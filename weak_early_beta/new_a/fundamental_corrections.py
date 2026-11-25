"""Explicit, append-only editorial corrections; never mutate analysis receipts."""

from copy import deepcopy
import datetime as dt
import os
from pathlib import Path
import re
from uuid import uuid4

from .files import atomic_write, digest, file_sha, private_root, read

SCHEMA = "NEW_A_FUNDAMENTAL_EDITORIAL_CORRECTIONS_V1"
FIELDS = ("材料インパクト", "事業概要", "足元材料", "ファンダ要点", "注意点", "開示リンク", "Sources")
EDITABLE = {"材料インパクト", "注意点"}
LABELS = {"ポジティブ材料", "ネガティブ材料", "混在/要確認", "様子見"}
SHA = re.compile(r"[0-9a-f]{64}")


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def checked_entry(identity, entry):
    require(isinstance(entry, dict) and set(entry) == {"original", "corrected", "reason"},
            "invalid editorial correction entry")
    old, new = entry["original"], entry["corrected"]
    require(isinstance(old, dict) and isinstance(new, dict) and old != new
            and set(old) == set(new) == {"identity", "symbol", "signalDate", "analysisCutoff", "auditStatus", "fields"},
            "invalid editorial report shape")
    require(all(old[k] == new[k] for k in old if k != "fields") and old["auditStatus"] == "pass"
            and old["identity"] == old["signalDate"] + "|" + old["symbol"]
            and re.fullmatch(re.escape(old["symbol"] + "|" + old["signalDate"] + "|") + r"[1-9][0-9]*", identity),
            "editorial correction changed report identity or cutoff")
    for report in (old, new):
        fields = report["fields"]
        require(isinstance(fields, list) and len(fields) == len(FIELDS)
                and all(isinstance(f, dict) and set(f) == {"label", "text"} and f["label"] == label
                        and isinstance(f["text"], str) and 0 < len(f["text"].strip()) <= 16000
                        for f, label in zip(fields, FIELDS)), "invalid editorial report fields")
        impact = fields[0]["text"]
        require("：" in impact and impact.split("：", 1)[0] in LABELS and len(impact.split("：", 1)[1]) <= 90,
                "invalid editorial impact label")
    require(all(a == b for a, b in zip(old["fields"], new["fields"]) if a["label"] not in EDITABLE)
            and isinstance(entry["reason"], str) and 20 <= len(entry["reason"]) <= 2000,
            "editorial correction exceeds reviewed prose scope")
    return entry


def checked_ledger(value):
    require(isinstance(value, dict) and set(value) == {"schema", "scope", "previous_sha256", "review", "entries"}
            and value["schema"] == SCHEMA and value["scope"] == "presentation-prose-only"
            and (value["previous_sha256"] is None or SHA.fullmatch(value["previous_sha256"] or ""))
            and isinstance(value["review"], dict) and set(value["review"]) == {
                "source_version", "snapshot_sha256", "bundle_manifest_sha256", "reviewed_at", "method"}
            and all(SHA.fullmatch(value["review"][k] or "") for k in (
                "source_version", "snapshot_sha256", "bundle_manifest_sha256"))
            and value["review"]["method"] == "explicit-editorial-review-no-absence-inference"
            and isinstance(value["entries"], dict) and 0 < len(value["entries"]) <= 10000,
            "invalid editorial correction ledger")
    stamp = dt.datetime.fromisoformat(value["review"]["reviewed_at"].replace("Z", "+00:00"))
    require(stamp.tzinfo is not None, "editorial review timestamp requires timezone")
    for identity, entry in value["entries"].items():
        checked_entry(identity, entry)
    return value


def retained(root):
    folder = Path(root) / "fundamentals" / "editorial-corrections"
    pointer = folder / "latest.json"
    if not pointer.exists():
        return None
    require(folder.resolve() == folder and pointer.resolve() == pointer,
            "editorial correction pointer escaped private history")
    saved = read(pointer)
    require(set(saved) == {"sha256"} and SHA.fullmatch(saved["sha256"] or ""), "invalid editorial correction pointer")
    path = folder / (saved["sha256"] + ".json")
    require(path.resolve() == path and path.stat().st_size <= 32 * 1024 * 1024,
            "editorial correction escaped retained history")
    ledger = checked_ledger(read(path))
    require(digest(ledger) == saved["sha256"], "retained editorial correction bytes changed")
    return ledger


def normalize(rows, ledger):
    """Validate existing corrected bytes, then use original receipts for attachment."""
    if ledger is None:
        return
    for row in rows:
        entry = ledger["entries"].get(row["identity"])
        if entry is None or row.get("fundamental") is None:
            continue
        require(row["symbol"] == entry["original"]["symbol"]
                and row["signalDate"] == entry["original"]["signalDate"]
                and row.get("analysisCutoff") == entry["original"]["analysisCutoff"]
                and row["fundamental"] in (entry["original"], entry["corrected"]),
                "editorial source report differs from the reviewed original")
        row["fundamental"] = deepcopy(entry["original"])


def apply(rows, ledger):
    if ledger is None:
        return
    for row in rows:
        entry = ledger["entries"].get(row["identity"])
        if entry is None:
            continue
        require(row.get("fundamental") == entry["original"]
                and row.get("analysisCutoff") == entry["original"]["analysisCutoff"],
                "editorial correction has no matching verified analysis")
        row["fundamental"] = deepcopy(entry["corrected"])


def register(repo, review_file, expected_sha256):
    """Retain reviewed prose only for the selected source's completed generation.

    This does not publish, detect, research, notify, or rewrite the producer.
    The existing publish command rebuilds a presentation-only bundle afterwards.
    """
    from .fundamentals import approved_recovery_source, _manifest, _rows

    repo = Path(repo).resolve()
    source = approved_recovery_source(repo)
    root = private_root(repo)
    config = read(repo / ".cache/weak_early_beta/daily-runner.config.json")
    runtime = Path(config["runtimeDir"])
    require(runtime.resolve() == runtime and runtime.is_relative_to(repo)
            and not any((runtime / name).exists() for name in ("daily.lock", "fundamental-recovery.lock")),
            "editorial correction cannot compete with a live daily or research owner")
    lease = runtime / "fundamental-correction.lock"
    with lease.open("x", encoding="utf8") as stream:
        stream.write(str(os.getpid()) + ":" + source + ":" + str(uuid4()) + "\n")
    lease_sha = file_sha(lease)
    try:
        path = Path(review_file).resolve(strict=True)
        require(SHA.fullmatch(expected_sha256 or "") and path.stat().st_size <= 32 * 1024 * 1024
                and file_sha(path) == expected_sha256, "exact reviewed editorial bytes required")
        ledger = checked_ledger(read(path))
        previous = retained(root)
        if previous == ledger:
            return {"schema": SCHEMA, "sha256": digest(ledger), "reports": len(ledger["entries"]),
                    "same_ledger_replay": True, "published": False,
                    "notifications_sent": 0, "detection_executed": False}
        run_file, daily_file = root / "latest-run.json", runtime / "daily-latest.json"
        frozen = {p: file_sha(p) for p in (run_file, daily_file, root / "latest-publication.json")}
        run, daily, published = (read(p) for p in frozen)
        require(daily.get("ok") is True and daily.get("completedAt")
                and daily.get("date") == run.get("latest_session") and run.get("dry_run") is False
                and run.get("detection_executed") is True and not run.get("delayed_recovery")
                and published.get("published") is True and published.get("active_readback_verified") is True
                and published.get("snapshot_sha256") == run["snapshot_sha256"]
                and published.get("source_version") == run["source_version"],
                "editorial correction requires the still-current completed published generation")
        bundle = Path(run["bundle_directory"])
        require(bundle.resolve() == bundle and bundle.is_relative_to(root / "runs"), "unsafe editorial base bundle")
        manifest, _ = _manifest(bundle)
        require(ledger["review"]["source_version"] == run["source_version"] == manifest["source_version"]
                and ledger["review"]["snapshot_sha256"] == run["snapshot_sha256"] == manifest["daily_snapshot_sha256"]
                and ledger["review"]["bundle_manifest_sha256"] == file_sha(bundle / "manifest.json"),
                "editorial review differs from the current immutable bundle")
        require(ledger["previous_sha256"] == (digest(previous) if previous else None)
                and (previous is None or all(ledger["entries"].get(k) == v for k, v in previous["entries"].items())),
                "editorial correction must preserve its append-only predecessor")
        rows = {row["identity"]: row for row in _rows(bundle, manifest)}
        for key, entry in ledger["entries"].items():
            require(key in rows and rows[key].get("fundamental") in (entry["original"], entry["corrected"])
                    and rows[key].get("analysisCutoff") == entry["original"]["analysisCutoff"],
                    "editorial review has no matching current report")
        require(all(file_sha(p) == sha for p, sha in frozen.items())
                and not (runtime / "daily.lock").exists() and not (runtime / "fundamental-recovery.lock").exists(),
                "producer changed during editorial review")
        folder = root / "fundamentals" / "editorial-corrections"
        sha = digest(ledger)
        saved = folder / (sha + ".json")
        if saved.exists():
            require(read(saved) == ledger, "saved editorial ledger changed")
        else:
            atomic_write(saved, ledger)
        atomic_write(folder / "latest.json", {"sha256": sha})
        require(retained(root) == ledger, "editorial correction readback differs")
        return {"schema": SCHEMA, "sha256": sha, "reports": len(ledger["entries"]),
                "published": False, "notifications_sent": 0, "detection_executed": False}
    finally:
        require(file_sha(lease) == lease_sha, "editorial correction ownership changed; preserve the lease")
        lease.unlink()
