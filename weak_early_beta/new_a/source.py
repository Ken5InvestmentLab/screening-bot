"""既存Cloud取得・品質検査の保存コードから抽出。価格や修復条件は変更しない。"""
import json,os,re,sys,tempfile
from pathlib import Path
from uuid import uuid4
import pandas as pd
from ..progress import daily_phase

def _fixed_path(repo, value, *, file=True):
    """A finite host record may refer only to this repository's private inputs."""
    repo = Path(repo).resolve()
    relative = value.get("path") if isinstance(value, dict) else None
    if not isinstance(relative, str) or not relative or Path(relative).anchor:
        raise ValueError("fixed source requires a relative private path")
    path = (repo / relative).resolve()
    private = (repo / ".cache/weak_early_beta").resolve()
    if not private.is_relative_to(repo) or path == private or not path.is_relative_to(private):
        raise ValueError("fixed source path escapes private inputs")
    if file:
        expected = value.get("sha256")
        if not re.fullmatch(r"[a-f0-9]{64}", expected or "") or not path.is_file():
            raise ValueError("fixed source file or hash is missing")
        from ..model import sha256
        if sha256(path) != expected:
            raise ValueError("fixed source file hash changed")
    elif not path.is_dir():
        raise ValueError("fixed source directory is missing")
    return path

def _fixed_source_inputs(repo, args, context):
    """Verify the exact decision inputs; never obtain today's JPX population."""
    from ..acquisition import AcquisitionArchive
    from ..model import sha256
    from ..restrictions import exclude_delisted_universe

    if (context.get("schema") != "NEW_A_FIXED_SOURCE_RECOVERY_V1"
            or context.get("target_date") != "2026-11-17"
            or getattr(args, "as_of", None) != context["target_date"]
            or context.get("period") != "5y" or args.period != context["period"]
            or args.refresh_live or getattr(args, "new_a_isolated", False)):
        raise ValueError("fixed source target or live acquisition differs")
    original = _fixed_path(repo, context["archive"], file=False)
    archive_ref = context["archive"]
    manifest_path = _fixed_path(repo, {"path": str((original / "manifest.json").relative_to(repo)),
                                      "sha256": archive_ref.get("manifest_sha256")})
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    original_context = manifest.get("context", {})
    tickers = original_context.get("tickers")
    if (manifest.get("identity") != "CLOUD_ACQUISITION_V1"
            or manifest.get("status") != "acquiring"
            or original_context.get("date") != context["target_date"]
            or original_context.get("period") != context["period"]
            or not isinstance(tickers, list) or not tickers
            or len(tickers) != len(set(tickers))
            or any(not isinstance(t, str) or not re.fullmatch(r"[0-9A-Z]{4}\.T", t) for t in tickers)
            or type(manifest.get("requests")) is not int
            or not 0 < manifest["requests"] <= 1000
            or manifest["requests"] != archive_ref.get("request_count")):
        raise ValueError("fixed source original acquisition context differs")
    previous_path = _fixed_path(repo, context["previous_corpus"])
    previous_quality_path = _fixed_path(repo, context["previous_quality"])
    previous_quality = json.loads(previous_quality_path.read_text(encoding="utf-8"))
    previous_sha = context["previous_corpus"]["sha256"]
    if (previous_sha != original_context.get("previousSourceSha256")
            or previous_quality.get("identity") != "CLOUD_SOURCE_QUALITY_V1"
            or previous_quality.get("daily_sha256") != previous_sha):
        raise ValueError("fixed source previous quality or acquisition lineage differs")
    restriction_path = _fixed_path(repo, context["restriction_snapshot"])
    restriction = json.loads(restriction_path.read_text(encoding="utf-8"))
    if (restriction.get("version") != 2 or restriction.get("as_of") != context["target_date"]
            or not isinstance(restriction.get("symbols"), list)
            or not restriction["symbols"]):
        raise ValueError("fixed source original restriction snapshot differs")
    # The pre-run official month-end workbook supplies presentation labels. The
    # original archive, independently, fixes every decision ticker and its order.
    workbook = _fixed_path(repo, context["official_workbook"])
    listed = pd.read_excel(workbook, dtype={"コード": str})
    date_col = next(c for c in listed.columns if str(c).strip() == "日付")
    if listed.empty or set(listed[date_col].astype(str)) != {"20261031"}:
        raise ValueError("fixed source label reference is not the pinned pre-run month-end edition")
    market_col = next(c for c in listed.columns if "市場" in str(c) and "区分" in str(c))
    code_col = next(c for c in listed.columns if str(c).strip() == "コード")
    name_col = next(c for c in listed.columns if "銘柄名" in str(c))
    market = listed[market_col].astype(str)
    keep = market.str.contains("プライム|スタンダード|グロース", regex=True)
    keep &= market.str.contains("内国株式", regex=False)
    universe = listed.loc[keep, [code_col, name_col, market_col]].copy()
    universe.columns = ["code", "name", "market"]
    universe["code"] = universe["code"].astype(str).str.strip()
    universe = universe[universe["code"].str.match(r"^[0-9A-Z]{4}$", na=False)].drop_duplicates("code")
    universe["ticker"] = universe["code"] + ".T"
    universe = universe.reset_index(drop=True)
    universe, excluded = exclude_delisted_universe(universe, restriction["symbols"], context["target_date"])
    if universe["ticker"].astype(str).tolist() != tickers or universe["name"].isna().any():
        raise ValueError("fixed source official reference differs from original ticker sequence")

    def verify_archive(directory):
        if sha256(directory / "manifest.json") != archive_ref.get("manifest_sha256"):
            raise ValueError("fixed source replay manifest changed")
        archive = AcquisitionArchive(directory, original_context, replay=True)
        archive.sequence = manifest["requests"]
        inventory = archive.verified_revision_info()
        if inventory["responseInventorySha256"] != archive_ref.get("inventory_sha256"):
            raise ValueError("fixed source response inventory changed")
        evidence = archive_ref.get("independent_evidence")
        if not isinstance(evidence, list) or not evidence:
            raise ValueError("fixed source independent evidence pins required")
        for pin in evidence:
            local = pin.get("path") if isinstance(pin, dict) else None
            if not isinstance(local, str) or Path(local).anchor:
                raise ValueError("fixed source independent evidence path differs")
            path = (directory / local).resolve()
            if not path.is_relative_to(directory / "jpx-evidence"):
                raise ValueError("fixed source independent evidence escapes archive")
            _fixed_path(repo, {"path": str(path.relative_to(repo)), "sha256": pin.get("sha256")})
        archive.sequence = 0
        archive.network_fallback_allowed = False
        return archive

    verify_archive(original)
    completed = context.get("completed_cache")
    if completed is not None:
        corpus = _fixed_path(repo, completed["corpus"])
        quality = _fixed_path(repo, completed["quality"])
        prior_quality = json.loads(quality.read_text(encoding="utf-8"))
        if (Path(args.daily_corpus).resolve() != corpus
                or quality != corpus.with_suffix(".source-quality.json")
                or prior_quality.get("identity") != "CLOUD_SOURCE_QUALITY_V1"
                or prior_quality.get("daily_sha256") != completed["corpus"]["sha256"]
                or completed.get("original_manifest_sha256") != archive_ref["manifest_sha256"]
                or completed.get("original_inventory_sha256") != archive_ref["inventory_sha256"]
                or completed.get("previous_source_sha256") != previous_sha):
            raise ValueError("fixed source completed cache lineage differs")
        archive = None
    else:
        corpus = Path(args.daily_corpus).resolve()
        if corpus != previous_path or previous_quality_path != corpus.with_suffix(".source-quality.json"):
            raise ValueError("fixed source previous corpus path differs")
        replay_path = Path(getattr(args, "retained_acquisition", "")).resolve()
        replay_path = _fixed_path(repo, {"path": str(replay_path.relative_to(repo))}, file=False)
        if replay_path == original:
            raise ValueError("fixed source requires a separate execution replay copy")
        archive = verify_archive(replay_path)
    return {"restrictions": restriction["symbols"], "universe": universe,
            "excluded": excluded, "archive": archive, "daily_path": corpus,
            "completed_cache": completed is not None,
            "reference": {"kind": "PRE_RUN_OFFICIAL_MONTH_END_REFERENCE",
                          "workbook_sha256": context["official_workbook"]["sha256"],
                          "original_response_bytes_equal_claimed": False,
                          "manifest_sha256": archive_ref["manifest_sha256"],
                          "restriction_sha256": context["restriction_snapshot"]["sha256"]}}
def _write_receipt(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
def _write_daily_cache(frame: pd.DataFrame, path: Path) -> None:
    """Keep the prior price/action evidence intact if a large CSV write fails."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        frame.to_csv(temporary, index=False, encoding="utf-8", lineterminator="\n", date_format="%Y-%m-%d")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
def acquire_and_validate(args):
    # Heavy TV-free runtime dependencies are needed only for the daily scorer;
    # report/bootstrap operations stay lightweight and deterministic.
    from .. import model
    from ..restrictions import (
        DEFAULT_RESTRICTION_SNAPSHOT, exclude_delisted_universe,
        fetch_jpx_restricted_symbols, preserve_delisted_history,
        quarantine_restricted_detections, restricted_mask,
    )

    from .operational_admission import source_context
    repo = Path(__file__).resolve().parents[2]
    finite_context = source_context(repo, args)
    finite = _fixed_source_inputs(repo, args, finite_context) if finite_context is not None else None

    retained = getattr(args, "retained_acquisition", None)
    acquire = bool(args.refresh_live or retained) and not (finite and finite["completed_cache"])
    archive = None

    # Fail closed before any vendor acquisition: a stale monthly JPX universe
    # can still contain securities delisted since its publication.
    tradability_date = getattr(args, "as_of", None) or str(pd.Timestamp.now(tz="Asia/Tokyo").date())
    with daily_phase("jpx-tradability"):
        restrictions = finite["restrictions"] if finite else fetch_jpx_restricted_symbols(
            tradability_date,
            Path(getattr(args, "restriction_snapshot", DEFAULT_RESTRICTION_SNAPSHOT)),
        )

    company_names: dict[str, str] = {}
    daily_path = finite["daily_path"] if finite else Path(args.daily_corpus)
    source_revision = {}
    acquisition_exclusions = {}
    if acquire:
        from ..corporate_actions import fetch_daily
        from ..acquisition import AcquisitionArchive

        with daily_phase("live-acquisition"):
            if finite:
                universe, excluded_universe = finite["universe"], finite["excluded"]
            else:
                universe = model.base.jpx_universe()
                universe, excluded_universe = exclude_delisted_universe(universe, restrictions, tradability_date)
            # The old cache is evidence for detecting unannounced source rebases;
            # it must not be treated as action-aware input merely because it exists.
            with daily_phase("previous-cache-read"):
                try:
                    previous = model.read_daily_csv(daily_path) if daily_path.exists() else None
                except MemoryError:
                    if finite is None and not retained and not getattr(args, "new_a_isolated", False):
                        print(json.dumps({
                            "identity": "NEW_A_PRE_PROVIDER_CACHE_FAILURE_V1",
                            "reason": "memory",
                            "phase": "previous-cache-read",
                        }, separators=(",", ":")), file=sys.stderr, flush=True)
                    raise
            if previous is not None:
                previous.attrs["source_sha256"] = model.sha256(daily_path)
                quality_path = daily_path.with_suffix(".source-quality.json")
                quality = json.loads(quality_path.read_text(encoding="utf-8")) if quality_path.exists() else {}
                matching_quality = (quality.get("identity") == "CLOUD_SOURCE_QUALITY_V1"
                                    and quality.get("daily_sha256") == previous.attrs["source_sha256"])
                if matching_quality:
                    holds = quality.get("source_revision", {}).get("jpxHolds", [])
                    if holds:
                        previous.attrs["jpx_hold_lineage"] = {"dailySha256": previous.attrs["source_sha256"], "holds": holds}
                    from ..reviewed_off_session_actions import PRIOR_AUDIT_ATTR

                    # Pandas deep-copies attrs: retain only the small reviewed
                    # journal lineage, never the multi-million-row quality audit.
                    retention = quality.get("source_revision", {}).get("retainedOffSessionActions", [])
                    if retention:
                        previous.attrs[PRIOR_AUDIT_ATTR] = {
                            "dailySha256": previous.attrs["source_sha256"], "actions": retention,
                        }
                    from ..reviewed_provider_restorations import (
                        NOVEMBER_AUDIT_ATTR,
                        PRIOR_AUDIT_ATTR as RESTORATION_AUDIT_ATTR,
                    )

                    november_restorations = quality.get("source_revision", {}).get("reviewedNovember9Restorations")
                    if november_restorations is not None:
                        previous.attrs[NOVEMBER_AUDIT_ATTR] = {
                            "dailySha256": previous.attrs["source_sha256"],
                            "restorations": november_restorations,
                        }

                    restorations = quality.get("source_revision", {}).get("reviewedProviderRestorations", [])
                    if restorations:
                        previous.attrs[RESTORATION_AUDIT_ATTR] = {
                            "dailySha256": previous.attrs["source_sha256"],
                            "restorations": restorations,
                        }
                delisted_codes = {row["code"] for row in restrictions if row.get("delisting_date")
                                  and not (row.get("relisting_date") and row["relisting_date"] <= tradability_date)}
                if previous["symbol"].isin(delisted_codes).any():
                    if not matching_quality:
                        raise RuntimeError("delisted history requires a matching source-quality receipt")
                del quality
            archive_path = Path(retained) if retained else Path(os.environ.get(
                "CLOUD_DAILY_ACQUISITION_DIR",
                str(daily_path.parent / "acquisitions" / f"{tradability_date}-{uuid4().hex}"),
            ))
            archive = finite["archive"] if finite else AcquisitionArchive(archive_path, {
                "date": tradability_date, "period": args.period,
                "tickers": universe.get("ticker", universe["code"].astype(str) + ".T").astype(str).tolist(),
                "previousSourceSha256": previous.attrs.get("source_sha256") if previous is not None else None,
            }, replay=bool(retained))
            print(json.dumps({"identity": "CLOUD_DAILY_PHASE_V1", "stage": "acquisition-evidence",
                              "event": "replay" if retained else "retaining", "directory": str(archive.directory)}),
                  file=sys.stderr, flush=True)
            try:
                raw = fetch_daily(universe, args.period, previous=previous, archive=archive)
            except BaseException as error:
                archive.mark("failed", error=f"{type(error).__name__}: {error}")
                raise
            if finite and archive.sequence != archive.manifest["requests"]:
                raise ValueError("fixed source replay did not consume every original request")
            archive.mark("source_validated")
            source_revision = raw.attrs.get("source_revision_receipt", {})
            raw, acquisition_exclusions = preserve_delisted_history(
                previous, raw, restrictions, tradability_date,
                previous_source_sha256=previous.attrs["source_sha256"] if previous is not None else None,
            )
            acquisition_exclusions["excluded_universe_symbols"] = sorted(excluded_universe["code"].astype(str).tolist())
            del previous
        with daily_phase("source-cache-write"):
            if finite:
                _fixed_source_inputs(repo, args, finite_context)
                if pd.to_datetime(raw["date"]).max().date().isoformat() != tradability_date:
                    raise ValueError("fixed source replay did not reach the target session")
            _write_daily_cache(raw, daily_path)
        del raw
        company_names = universe.set_index("code")["name"].astype(str).to_dict()
    else:
        if not daily_path.exists():
            raise FileNotFoundError(f"daily corpus not found: {daily_path}")
        if finite:
            company_names = finite["universe"].set_index("code")["name"].astype(str).to_dict()
        elif args.refresh_universe:
            universe = model.base.jpx_universe()
            company_names = universe.set_index("code")["name"].astype(str).to_dict()
    source_hash = model.sha256(daily_path)
    with daily_phase("cache-read-and-validation"):
        raw = model.read_daily(daily_path)
    from ..corporate_actions import source_quality_receipt

    with daily_phase("source-quality"):
        source_quality = source_quality_receipt(raw)
    if finite and pd.to_datetime(raw["date"]).max().date().isoformat() != tradability_date:
        raise ValueError("fixed source cache did not reach the target session")
    quality_path = daily_path.with_suffix(".source-quality.json")
    if not acquire:
        from ..jpx_holds import verify_cached_lineage
        prior_quality = json.loads(quality_path.read_text(encoding="utf-8")) if quality_path.exists() else {}
        verify_cached_lineage(raw, prior_quality, source_hash)
    if not acquire and quality_path.exists():
        previous_quality = json.loads(quality_path.read_text(encoding="utf-8"))
        if previous_quality.get("daily_sha256") == source_hash:
            source_revision = previous_quality.get("source_revision", {})
            acquisition_exclusions = previous_quality.get("acquisition_exclusions", {})
    if finite and finite["completed_cache"]:
        if any(previous_quality.get(key) != value for key, value in source_quality.items()):
            raise ValueError("fixed source cached quality does not match verified rows")
    else:
        _write_receipt(quality_path, {**source_quality, "daily_sha256": source_hash, "source_revision": source_revision,
                                    "acquisition_exclusions": acquisition_exclusions})
    if archive:
        archive.mark("cached", dailySha256=source_hash)
    quality_dates = sorted(source_quality["quarantinedDates"])
    source_quality = {key: value for key, value in source_quality.items() if key not in {"issues", "quarantinedDates"}}
    source_quality.update(
        quarantinedDateCount=len(quality_dates),
        firstQuarantinedDate=quality_dates[0] if quality_dates else None,
        lastQuarantinedDate=quality_dates[-1] if quality_dates else None,
    )
    source_quality.update(audit_path=str(quality_path), audit_sha256=model.sha256(quality_path))
    source_revision = {
        **{key: value for key, value in source_revision.items() if key not in {"acceptedRepairs", "quarantinedComparisons"}},
        "acceptedRepairs": [
            {key: value for key, value in repair.items() if key != "differences"}
            for repair in source_revision.get("acceptedRepairs", [])
        ],
        "quarantinedComparisonSymbolCount": len(source_revision.get("quarantinedComparisons", [])),
    }
    result = dict(frame=raw,daily_path=daily_path,source_hash=source_hash,company_names=company_names,restrictions=restrictions,source_quality=source_quality,source_revision=source_revision,acquisition_exclusions=acquisition_exclusions,quality_path=quality_path,acquisition_evidence=archive.info() if archive else None)
    if finite:
        result["fixed_input_reference"] = finite["reference"]
    return result
