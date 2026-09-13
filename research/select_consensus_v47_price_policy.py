from __future__ import annotations

import argparse
import json
from pathlib import Path

PRIMARY_COST = 0.005
MIN_DEV_N = 20
MEAN_TIE_PP = 0.50
TOP3_TIE_PP = 0.25
ARMS = ("NOCAP", "CAP1000_PIT")


def _req(st: dict, key: str) -> float:
    if key not in st:
        raise RuntimeError(f"missing metric: {key}")
    return float(st[key])


def choose_dev(dev: dict[str, dict]) -> dict:
    for arm in ARMS:
        if arm not in dev:
            raise RuntimeError(f"missing arm: {arm}")
        if int(dev[arm].get("n", 0)) < MIN_DEV_N:
            raise RuntimeError(f"{arm}: development n < {MIN_DEV_N}")

    a = dev["NOCAP"]
    b = dev["CAP1000_PIT"]
    ma = _req(a, "mean_net_0p5_pct")
    mb = _req(b, "mean_net_0p5_pct")

    if abs(ma - mb) >= MEAN_TIE_PP:
        winner = "NOCAP" if ma > mb else "CAP1000_PIT"
        reason = "higher development mean after 0.5% cost"
    else:
        ta = _req(a, "top3_ex_net_0p5_pct")
        tb = _req(b, "top3_ex_net_0p5_pct")
        if abs(ta - tb) >= TOP3_TIE_PP:
            winner = "NOCAP" if ta > tb else "CAP1000_PIT"
            reason = "mean tie; higher development Top3-excluded mean"
        else:
            da = _req(a, "median_net_0p5_pct")
            db = _req(b, "median_net_0p5_pct")
            if da != db:
                winner = "NOCAP" if da > db else "CAP1000_PIT"
                reason = "mean/Top3 tie; higher development median"
            else:
                winner = "NOCAP"
                reason = "full tie; simpler no-cap policy"

    return {
        "winner": winner,
        "reason": reason,
        "development": dev,
        "nonwinner_h2_must_remain_unopened": True,
    }


def validate_winner(winner: str, h2: dict) -> dict:
    if winner not in ARMS:
        raise RuntimeError(f"invalid winner: {winner}")
    if h2.get("arm") != winner:
        raise RuntimeError(
            f"validation arm mismatch: expected {winner}, got {h2.get('arm')}"
        )
    mean = _req(h2, "mean_net_0p5_pct")
    return {
        "arm": winner,
        "h2_mean_net_0p5_pct": mean,
        "continued_research_pass": bool(mean > 0.0),
        "diagnostics": h2,
        "note": (
            "Mean after 0.5% cost is the performance-first continuation gate. "
            "Median/Top3/tail/concentration remain mandatory diagnostics, not "
            "automatic vetoes solely because rare monster winners are allowed."
        ),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--development-json", required=True, type=Path)
    ap.add_argument("--validation-json", type=Path)
    ap.add_argument("--output", required=True, type=Path)
    a = ap.parse_args()

    dev_payload = json.loads(a.development_json.read_text(encoding="utf-8"))
    dev = dev_payload["development"]
    decision = choose_dev(dev)

    result = {
        "scope": "V47 clean PIT price-policy performance-first selector",
        "primary_cost_round_trip": PRIMARY_COST,
        "development_decision": decision,
        "validation_opened": False,
        "production_writes": False,
    }

    if a.validation_json is not None:
        h2 = json.loads(a.validation_json.read_text(encoding="utf-8"))
        result["validation_opened"] = True
        result["validation"] = validate_winner(decision["winner"], h2)

    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
