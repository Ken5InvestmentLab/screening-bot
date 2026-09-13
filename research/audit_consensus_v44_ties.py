from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


def exact_tie_counts(pool: pd.DataFrame) -> dict:
    gcols = ["date", "session"]
    groups = 0
    top1_tied = 0
    any_top10_tied = 0
    tied_rows = 0
    total_rows = 0
    top1_sizes = []

    for _, g in pool.groupby(gcols, sort=True):
        groups += 1
        x = g.sort_values(
            ["candidate_rank", "symbol"],
            ascending=[True, True],
        ).copy()
        total_rows += len(x)
        vc = x["cons_min"].value_counts(dropna=False)
        tied_values = set(vc[vc > 1].index.tolist())
        tied_rows += int(x["cons_min"].isin(tied_values).sum())
        if len(tied_values):
            any_top10_tied += 1
        top = float(x.iloc[0]["cons_min"])
        n_top = int(np.sum(np.isclose(x["cons_min"].astype(float), top, rtol=0, atol=0)))
        if n_top > 1:
            top1_tied += 1
            top1_sizes.append(n_top)

    return {
        "groups": groups,
        "groups_with_top1_cons_min_tie": top1_tied,
        "top1_tie_group_fraction": float(top1_tied / groups) if groups else None,
        "top1_tie_group_size_distribution": {
            "n": len(top1_sizes),
            "min": int(min(top1_sizes)) if top1_sizes else None,
            "median": float(np.median(top1_sizes)) if top1_sizes else None,
            "max": int(max(top1_sizes)) if top1_sizes else None,
        },
        "groups_with_any_tie_within_top10": any_top10_tied,
        "any_tie_group_fraction": float(any_top10_tied / groups) if groups else None,
        "candidate_rows": total_rows,
        "candidate_rows_in_exact_cons_min_ties": tied_rows,
        "candidate_tie_fraction": float(tied_rows / total_rows) if total_rows else None,
    }


def selected_tie_exposure(pool: pd.DataFrame, selected: pd.DataFrame) -> dict:
    # Outcome-free: only asks whether the selected row's score is shared by
    # another candidate in the same date/session pool.
    key = ["date", "session"]
    base = pool[key + ["symbol", "cons_min"]].copy()
    sel = selected[key + ["symbol", "cons_min"]].copy()
    exposed = 0
    total = 0
    alt_counts = []
    for row in sel.itertuples(index=False):
        g = base[
            (base["date"] == row.date)
            & (base["session"] == row.session)
        ]
        same = g[np.isclose(g["cons_min"].astype(float), float(row.cons_min), rtol=0, atol=0)]
        total += 1
        alts = int(len(same) - 1)
        alt_counts.append(max(0, alts))
        if alts > 0:
            exposed += 1
    return {
        "selected_rows": total,
        "selected_rows_with_score_tied_to_alternative": exposed,
        "selected_tie_exposure_fraction": float(exposed / total) if total else None,
        "alternative_count_distribution": {
            "median": float(np.median(alt_counts)) if alt_counts else None,
            "max": int(max(alt_counts)) if alt_counts else None,
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", required=True, type=Path)
    ap.add_argument("--selected", action="append", default=[], type=Path)
    ap.add_argument("--output", required=True, type=Path)
    a = ap.parse_args()

    pool = pd.read_csv(a.pool, dtype={"symbol": str})
    required = {"date", "session", "symbol", "cons_min", "candidate_rank"}
    missing = required - set(pool.columns)
    if missing:
        raise RuntimeError(f"pool missing columns: {sorted(missing)}")

    out = {
        "scope": "outcome-free exact cons_min tie prevalence audit",
        "pool": exact_tie_counts(pool),
        "selected": {},
        "returns_opened": False,
        "production_writes": False,
    }
    for p in a.selected:
        s = pd.read_csv(p, dtype={"symbol": str})
        out["selected"][p.name] = selected_tie_exposure(pool, s)

    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
