from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

import no_tv_v47_dev_price_policy as dev
import no_tv_v47_h2_winner_validation as h2
from no_tv_v47_midterm_diagnostic import gross_stats


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--nocap-dev", required=True, type=Path)
    ap.add_argument("--nocap-validation-blind", required=True, type=Path)
    ap.add_argument("--frozen-daily", required=True, type=Path)
    ap.add_argument("--restored-daily", required=True, type=Path)
    ap.add_argument("--preopen-spec", required=True, type=Path)
    ap.add_argument("--output-dir", required=True, type=Path)
    a = ap.parse_args()

    spec = json.loads(a.preopen_spec.read_text(encoding="utf-8"))
    if spec.get("label") != "MIDTERM_DIAGNOSTIC_NOT_PROMOTION_EVIDENCE":
        raise RuntimeError("missing diagnostic-only label")
    if spec.get("promotion_evidence") is not False:
        raise RuntimeError("diagnostic cannot be promotion evidence")
    if spec.get("h1_leader_fixed_before_h2_open") != "NOCAP":
        raise RuntimeError("H2 diagnostic may open only frozen H1 leader NOCAP")
    if spec.get("cost_round_trip") != 0.0:
        raise RuntimeError("H2 diagnostic must use cost 0%")
    if spec.get("selection_restrictions", {}).get("open_CAP1000_PIT_H2") is not False:
        raise RuntimeError("CAP1000_PIT H2 must stay closed")

    devf = pd.read_parquet(a.nocap_dev)
    blind = pd.read_parquet(a.nocap_validation_blind)
    if "canonical_ret_5bd" in blind.columns or "legacy_ret_5bd" in blind.columns:
        raise RuntimeError("validation-blind input already contains target returns")

    labels = h2.load_label_map(a.frozen_daily, a.restored_daily)
    h2f = h2.attach_h2_labels(blind, labels)
    history = pd.concat([devf, h2f], ignore_index=True, sort=False)

    day_ix = dev.trading_day_index(a.frozen_daily)
    dev_raw = dev.prequential_select(devf, "NOCAP")
    dev_selected = dev.strict5_no_replacement(dev_raw, day_ix)

    h2_raw = h2.prequential_h2(history)
    h2_selected = h2.strict5_with_carry(h2_raw, dev_selected, day_ix)
    metrics = gross_stats(h2_selected)

    out = a.output_dir
    out.mkdir(parents=True, exist_ok=True)
    h2_selected.to_csv(out / "v47_midterm_h2_selected_nocap.csv", index=False)
    payload = {
        "label": "MIDTERM_DIAGNOSTIC_NOT_PROMOTION_EVIDENCE",
        "arm": "NOCAP",
        "validation_period": [h2.VALID_START, h2.VALID_END],
        "endpoint": "next official XTKS open -> D+5 close",
        "cost_round_trip": 0.0,
        "win_definition": "gross canonical_ret_5bd > 0",
        "policy": dev.POLICY,
        "strict_same_symbol_cooldown_sessions": 5,
        "cooldown_state_carried_from_h1": True,
        "coverage_bypassed": True,
        "missing_pairs_interpolated": False,
        "synthetic_bars": False,
        "h1_leader_fixed_before_h2_open": "NOCAP",
        "h2": metrics,
        "h2_now_opened_for_diagnostic": True,
        "h2_remains_untouched_holdout": False,
        "cap1000_pit_h2_opened": False,
        "2026_opened": False,
        "retune_same_family_after_open": False,
        "promotion_evidence": False,
        "production_writes": False,
    }
    (out / "v47_midterm_h2_diagnostic.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
