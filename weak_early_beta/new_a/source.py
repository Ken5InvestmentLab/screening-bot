"""既存Cloud取得・品質検査の保存コードから抽出。価格や修復条件は変更しない。"""
import json,os,sys,tempfile
from pathlib import Path
from uuid import uuid4
import pandas as pd
from ..progress import daily_phase
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

    retained = getattr(args, "retained_acquisition", None)
    acquire = bool(args.refresh_live or retained)
    archive = None

    # Fail closed before any vendor acquisition: a stale monthly JPX universe
    # can still contain securities delisted since its publication.
    tradability_date = getattr(args, "as_of", None) or str(pd.Timestamp.now(tz="Asia/Tokyo").date())
    with daily_phase("jpx-tradability"):
        restrictions = fetch_jpx_restricted_symbols(
            tradability_date,
            Path(getattr(args, "restriction_snapshot", DEFAULT_RESTRICTION_SNAPSHOT)),
        )

    company_names: dict[str, str] = {}
    daily_path = Path(args.daily_corpus)
    source_revision = {}
    acquisition_exclusions = {}
    if acquire:
        from ..corporate_actions import fetch_daily
        from ..acquisition import AcquisitionArchive

        with daily_phase("live-acquisition"):
            universe = model.base.jpx_universe()
            universe, excluded_universe = exclude_delisted_universe(universe, restrictions, tradability_date)
            # The old cache is evidence for detecting unannounced source rebases;
            # it must not be treated as action-aware input merely because it exists.
            previous = (
                pd.read_csv(daily_path, parse_dates=["date"], dtype={"symbol": str})
                if daily_path.exists() else None
            )
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
            archive = AcquisitionArchive(archive_path, {
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
            archive.mark("source_validated")
            source_revision = raw.attrs.get("source_revision_receipt", {})
            raw, acquisition_exclusions = preserve_delisted_history(
                previous, raw, restrictions, tradability_date,
                previous_source_sha256=previous.attrs["source_sha256"] if previous is not None else None,
            )
            acquisition_exclusions["excluded_universe_symbols"] = sorted(excluded_universe["code"].astype(str).tolist())
            del previous
        with daily_phase("source-cache-write"):
            _write_daily_cache(raw, daily_path)
        del raw
        company_names = universe.set_index("code")["name"].astype(str).to_dict()
    else:
        if not daily_path.exists():
            raise FileNotFoundError(f"daily corpus not found: {daily_path}")
        if args.refresh_universe:
            universe = model.base.jpx_universe()
            company_names = universe.set_index("code")["name"].astype(str).to_dict()
    source_hash = model.sha256(daily_path)
    with daily_phase("cache-read-and-validation"):
        raw = model.read_daily(daily_path)
    from ..corporate_actions import source_quality_receipt

    with daily_phase("source-quality"):
        source_quality = source_quality_receipt(raw)
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
    return dict(frame=raw,daily_path=daily_path,source_hash=source_hash,company_names=company_names,restrictions=restrictions,source_quality=source_quality,source_revision=source_revision,acquisition_exclusions=acquisition_exclusions,quality_path=quality_path,acquisition_evidence=archive.info() if archive else None)
