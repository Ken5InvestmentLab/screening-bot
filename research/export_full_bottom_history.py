from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd

import optimize_screener as opt

START = pd.Timestamp("2026-03-05")
END = pd.Timestamp("2026-09-10")
SHEETS = ("alerts_raw", "signals_archive")


def fetch_retry(service, sheet: str):
    last = None
    for attempt in range(6):
        try:
            return opt.fetch(service, sheet)
        except Exception as exc:
            last = exc
            if attempt >= 5:
                raise
            delay = 2 ** attempt
            print(f"read retry {attempt + 1}/6 sheet={sheet} err={type(exc).__name__} sleep={delay}s", flush=True)
            time.sleep(delay)
    raise last


def rows_to_frame(values, sheet: str) -> pd.DataFrame:
    if not values:
        return pd.DataFrame()
    header_idx = None
    for i, row in enumerate(values[:20]):
        norm = [str(x).strip() for x in row]
        if "alert_id" in norm and "signal_type" in norm and "symbol_code" in norm:
            header_idx = i
            break
    if header_idx is None:
        raise RuntimeError(f"header not found: {sheet}")
    header = [str(x).strip() for x in values[header_idx]]
    body = values[header_idx + 1 :]
    width = len(header)
    rows = []
    for row in body:
        vals = list(row[:width]) + [""] * max(0, width - len(row))
        rows.append(vals[:width])
    df = pd.DataFrame(rows, columns=header)
    df["source_sheet"] = sheet
    return df


def derive_session(received_at: pd.Series) -> pd.Series:
    ts = pd.to_datetime(received_at, errors="coerce")
    # Production watchlist alerts arrive around 13:00 for the morning 4H bar
    # and around 15:32 for the afternoon bar. Map them to 09 / 13 session labels.
    return pd.Series(pd.NA, index=received_at.index, dtype="Int64").mask(ts.dt.hour < 14, 9).mask(ts.dt.hour >= 14, 13)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", default="research_artifacts/no_tv_teacher/full_bottom_history.csv")
    args = ap.parse_args()

    svc = opt.get_service()
    frames = []
    raw_counts = {}
    for sheet in SHEETS:
        values = fetch_retry(svc, sheet)
        frame = rows_to_frame(values, sheet)
        raw_counts[sheet] = int(len(frame))
        frames.append(frame)

    all_rows = pd.concat(frames, ignore_index=True)
    all_rows["signal_type"] = all_rows.get("signal_type", "").astype(str).str.upper().str.strip()
    all_rows["alert_id"] = all_rows.get("alert_id", "").astype(str).str.strip()
    all_rows["symbol_code"] = all_rows.get("symbol_code", "").astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
    all_rows["signal_date"] = pd.to_datetime(all_rows.get("signal_date"), errors="coerce")
    all_rows["received_at"] = all_rows.get("received_at", "").astype(str)
    all_rows = all_rows[(all_rows.signal_type == "BOTTOM") & all_rows.signal_date.notna()].copy()
    all_rows = all_rows[(all_rows.signal_date >= START) & (all_rows.signal_date <= END)].copy()
    all_rows = all_rows[all_rows.alert_id.ne("") & all_rows.symbol_code.ne("")].copy()

    # alerts_raw and signals_archive can overlap during archival transitions.
    # One alert_id is one production signal, so dedupe on alert_id.
    all_rows = all_rows.sort_values(["signal_date", "received_at", "source_sheet"])
    duplicate_alert_ids = int(all_rows.alert_id.duplicated(keep=False).sum())
    all_rows = all_rows.drop_duplicates("alert_id", keep="last").copy()
    all_rows["session"] = derive_session(all_rows.received_at)
    all_rows = all_rows[all_rows.session.isin([9, 13])].copy()
    all_rows["signal_date"] = all_rows.signal_date.dt.strftime("%Y-%m-%d")

    keep = ["signal_date", "session", "symbol_code", "alert_id", "received_at", "entry_price", "volume", "perf_5bd", "source_sheet"]
    for col in keep:
        if col not in all_rows.columns:
            all_rows[col] = ""
    out = all_rows[keep].sort_values(["signal_date", "session", "symbol_code", "alert_id"]).reset_index(drop=True)

    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(path, index=False, encoding="utf-8-sig")

    monthly = out.groupby(out.signal_date.str[:7]).size().astype(int).to_dict()
    summary = {
        "rows": int(len(out)),
        "date_min": out.signal_date.min() if len(out) else None,
        "date_max": out.signal_date.max() if len(out) else None,
        "symbols": int(out.symbol_code.nunique()) if len(out) else 0,
        "raw_sheet_rows": raw_counts,
        "overlap_rows_before_dedupe": duplicate_alert_ids,
        "duplicate_alert_ids_after_dedupe": int(out.alert_id.duplicated().sum()),
        "monthly": monthly,
        "session_counts": {str(k): int(v) for k, v in out.session.value_counts().sort_index().items()},
    }
    summary_path = path.with_suffix(".summary.json")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    # Guardrails. Exact row count can grow only if historical data is repaired, but it must remain near the audited 4,041.
    if len(out) < 3900:
        raise RuntimeError(f"teacher rows unexpectedly low: {len(out)}")
    if out.alert_id.duplicated().any():
        raise RuntimeError("duplicate alert_id remains")
    required_months = {"2026-03", "2026-04", "2026-05", "2026-06", "2026-07", "2026-08", "2026-09"}
    if not required_months.issubset(monthly):
        raise RuntimeError(f"missing teacher months: {sorted(required_months - set(monthly))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
