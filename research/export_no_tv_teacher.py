from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

import optimize_screener as opt

_ORIGINAL_FETCH = opt.fetch

def _retry_fetch(service, sheet):
    last = None
    for attempt in range(6):
        try:
            return _ORIGINAL_FETCH(service, sheet)
        except Exception as exc:
            last = exc
            if attempt >= 5:
                raise
            delay = 2 ** attempt
            print(f"Sheet read retry {attempt+1}/5 for {sheet}: {type(exc).__name__}; sleep {delay}s", flush=True)
            time.sleep(delay)
    raise last

# build_mega_report_feature_frames() uses module-global fetch.
opt.fetch = _retry_fetch


OUT = Path("research_artifacts/no_tv_teacher")


def clean_for_csv(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in out.columns:
        if out[col].dtype == "object":
            out[col] = out[col].map(
                lambda v: "|".join(map(str, v))
                if isinstance(v, (tuple, list, set, frozenset))
                else (json.dumps(v, ensure_ascii=False, sort_keys=True) if isinstance(v, dict) else v)
            )
    return out


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    confirmed, live = opt.build_mega_report_feature_frames()
    if confirmed is None or confirmed.empty:
        raise RuntimeError("confirmed teacher frame is empty")

    confirmed = confirmed.copy()
    stable_scores = opt.published_stable_score(
        confirmed,
        pd.Series(0, index=confirmed.index),
    )
    confirmed["teacher_stable_score"] = stable_scores.astype(int)
    confirmed["teacher_stable6"] = confirmed["teacher_stable_score"] == 6
    confirmed["teacher_win5"] = pd.to_numeric(confirmed["perf_5bd"], errors="coerce") > 0
    confirmed["teacher_hit10"] = pd.to_numeric(confirmed["perf_5bd"], errors="coerce") >= 0.10
    confirmed["teacher_lose10"] = pd.to_numeric(confirmed["perf_5bd"], errors="coerce") <= -0.10

    stable6 = confirmed[confirmed["teacher_stable6"]].copy()

    clean_for_csv(confirmed).to_csv(
        OUT / "teacher_bottom_confirmed.csv", index=False, encoding="utf-8-sig"
    )
    clean_for_csv(stable6).to_csv(
        OUT / "teacher_stable6_confirmed.csv", index=False, encoding="utf-8-sig"
    )
    if live is not None and not live.empty:
        clean_for_csv(live).to_csv(
            OUT / "teacher_live_unconfirmed.csv", index=False, encoding="utf-8-sig"
        )

    perf = pd.to_numeric(stable6.get("perf_5bd"), errors="coerce").dropna()
    decisive = perf[perf != 0]
    summary = {
        "evaluation_days": opt.EVALUATION_BACKTEST_DAYS,
        "confirmed_bottom_n": int(len(confirmed)),
        "stable6_n": int(len(stable6)),
        "stable6_avg": float(perf.mean()) if len(perf) else None,
        "stable6_median": float(perf.median()) if len(perf) else None,
        "stable6_win_rate": float((decisive > 0).mean()) if len(decisive) else None,
        "stable6_hit10": int((perf >= 0.10).sum()) if len(perf) else 0,
        "stable6_lose10": int((perf <= -0.10).sum()) if len(perf) else 0,
        "final_snapshot_rows": int(confirmed.get("_snapshot_final", pd.Series(False, index=confirmed.index)).fillna(False).sum()),
        "columns": list(map(str, confirmed.columns)),
    }
    (OUT / "teacher_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
