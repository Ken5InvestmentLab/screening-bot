from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable, Mapping, Sequence
import hashlib
import json


REQUIRED_SOURCE_TAGS = {"RAW_CAUSAL_INTRADAY"}
FORBIDDEN_SOURCE_TAGS = {"POSTCLOSE_RECON_ONLY", "DAILY_RESOLUTION_FALLBACK"}


@dataclass(frozen=True)
class ShadowCandidate:
    experiment_id: str
    model_freeze_id: str
    symbol: str
    signal_date: str
    bin_name: str
    feature_cutoff: str
    source_tag: str
    score: float | None = None
    rank: int | None = None
    payload_sha256: str | None = None

    @property
    def key(self) -> str:
        return "|".join((self.experiment_id, self.model_freeze_id, self.symbol, self.signal_date, self.bin_name))


def canonical_payload_sha256(payload: Mapping) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def validate_candidate(candidate: ShadowCandidate) -> None:
    if candidate.source_tag in FORBIDDEN_SOURCE_TAGS:
        raise ValueError(f"noncausal source tag: {candidate.source_tag}")
    if candidate.source_tag not in REQUIRED_SOURCE_TAGS:
        raise ValueError(f"unapproved source tag: {candidate.source_tag}")
    if not candidate.experiment_id or not candidate.model_freeze_id:
        raise ValueError("experiment_id and model_freeze_id are required")
    if not candidate.symbol or not candidate.signal_date or not candidate.bin_name or not candidate.feature_cutoff:
        raise ValueError("symbol/date/bin/cutoff are required")


def append_candidates(path: Path, candidates: Iterable[ShadowCandidate]) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing: set[str] = set()
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            existing.add(row["key"])

    added = 0
    skipped_duplicate = 0
    with path.open("a", encoding="utf-8") as f:
        for candidate in candidates:
            validate_candidate(candidate)
            if candidate.key in existing:
                skipped_duplicate += 1
                continue
            row = asdict(candidate)
            row["key"] = candidate.key
            row["status"] = "PENDING_5BD"
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            existing.add(candidate.key)
            added += 1
    return {"added": added, "skipped_duplicate": skipped_duplicate, "total_keys": len(existing)}


def maturity_dates(signal_date: str, sessions: Sequence[str]) -> tuple[str, str] | None:
    try:
        i = sessions.index(signal_date)
    except ValueError:
        return None
    if i + 5 >= len(sessions):
        return None
    return sessions[i + 1], sessions[i + 5]


def resolve_row(row: Mapping, daily_by_key: Mapping[tuple[str, str], Mapping], sessions: Sequence[str]) -> dict:
    out = dict(row)
    dates = maturity_dates(str(row["signal_date"]), sessions)
    if dates is None:
        out["status"] = "PENDING_5BD"
        return out
    entry_date, exit_date = dates
    entry = daily_by_key.get((str(row["symbol"]), entry_date))
    exit_ = daily_by_key.get((str(row["symbol"]), exit_date))
    if entry is None or exit_ is None:
        out.update(status="UNRESOLVED_ENDPOINT", entry_date=entry_date, exit_date=exit_date)
        return out
    try:
        entry_open = float(entry["open"])
        exit_close = float(exit_["close"])
    except (KeyError, TypeError, ValueError):
        out.update(status="UNRESOLVED_ENDPOINT", entry_date=entry_date, exit_date=exit_date)
        return out
    if entry_open <= 0 or exit_close <= 0:
        out.update(status="UNRESOLVED_ENDPOINT", entry_date=entry_date, exit_date=exit_date)
        return out
    out.update(
        status="RESOLVED",
        entry_date=entry_date,
        exit_date=exit_date,
        entry_open=entry_open,
        exit_close=exit_close,
        ret5bd_gross=exit_close / entry_open - 1.0,
    )
    return out


def resolve_shadow_file(input_path: Path, output_path: Path, daily_rows: Iterable[Mapping], sessions: Sequence[str]) -> dict:
    daily_by_key = {(str(r["symbol"]), str(r["date"])): r for r in daily_rows}
    rows = []
    for line in input_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(resolve_row(json.loads(line), daily_by_key, sessions))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows), encoding="utf-8")
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    return {"rows": len(rows), "status_counts": counts}
