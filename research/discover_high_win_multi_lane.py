"""Discover preregistered family winners using 2023-2024 only."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


TARGET = "target5_no"
BASE_FIELDS = ["date", "symbol", "med_ret5", "ret10", "tail_cdf", TARGET]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def stats(frame: pd.DataFrame) -> dict:
    x = frame[TARGET].to_numpy(float)
    ordered = np.sort(x)[::-1]
    return {
        "n": int(len(x)),
        "mean": float(np.mean(x)),
        "median": float(np.median(x)),
        "win": float(np.mean(x > 0)),
        "plus20": float(np.mean(x >= 0.20)),
        "minus10": float(np.mean(x <= -0.10)),
        "top3_excluded_mean": float(np.mean(ordered[3:])),
    }


def select(population: pd.DataFrame, atoms: list[str]) -> pd.DataFrame:
    ranked = population.copy()
    score_columns = []
    for atom in atoms:
        feature, direction = atom.split(":")
        column = f"rank__{feature}__{direction}"
        ranked[column] = ranked.groupby("date")[feature].rank(
            method="average", pct=True, ascending=direction == "LOW"
        )
        score_columns.append(column)
    ranked["score"] = ranked[score_columns].mean(axis=1)
    return (
        ranked.sort_values(
            ["date", "score", "tail_cdf", "symbol"],
            ascending=[True, True, False, True],
            kind="mergesort",
        )
        .drop_duplicates("date", keep="first")
        .copy()
    )


def order_key(record: dict) -> tuple:
    return (
        -record["min_year_win"],
        -record["aggregate_win"],
        -record["min_year_median"],
        -record["aggregate_top3_excluded_mean"],
        -record["aggregate_mean"],
        record["candidate_id"],
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tail-cache", type=Path, required=True)
    parser.add_argument("--prereg", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    contract = json.loads(args.prereg.read_text(encoding="utf-8"))
    if sha256(args.tail_cache) != contract["input"]["tail_sha256"]:
        raise RuntimeError("Tail input SHA-256 drift")
    features = sorted(
        {atom.split(":")[0] for variants in contract["families"].values() for atoms in variants for atom in atoms}
    )
    frame = pd.read_csv(
        args.tail_cache,
        usecols=list(dict.fromkeys(BASE_FIELDS + features)),
        dtype={"symbol": str},
        parse_dates=["date"],
    )
    # Fail closed: discovery frame contains no 2025/2026 row before target use.
    frame = frame[frame["date"].dt.year.isin([2023, 2024])].copy()
    if set(frame["date"].dt.year.unique()) != {2023, 2024}:
        raise RuntimeError("discovery years are not exactly 2023 and 2024")
    population = frame[
        frame["med_ret5"].le(0)
        & frame["ret10"].le(0.5735294117647058)
    ].copy()

    records = []
    identities: dict[str, set[tuple[str, str]]] = {}
    selected_rows: dict[str, pd.DataFrame] = {}
    for family, variants in contract["families"].items():
        for index, atoms in enumerate(variants, start=1):
            candidate_id = f"{family}_V{index}"
            chosen = select(population, atoms)
            by_year = {str(year): stats(group) for year, group in chosen.groupby(chosen["date"].dt.year)}
            aggregate = stats(chosen)
            record = {
                "candidate_id": candidate_id,
                "family": family,
                "atoms": atoms,
                "n_2023": by_year["2023"]["n"],
                "n_2024": by_year["2024"]["n"],
                "win_2023": by_year["2023"]["win"],
                "win_2024": by_year["2024"]["win"],
                "median_2023": by_year["2023"]["median"],
                "median_2024": by_year["2024"]["median"],
                "min_year_win": min(by_year["2023"]["win"], by_year["2024"]["win"]),
                "min_year_median": min(by_year["2023"]["median"], by_year["2024"]["median"]),
                "aggregate_n": aggregate["n"],
                "aggregate_mean": aggregate["mean"],
                "aggregate_median": aggregate["median"],
                "aggregate_win": aggregate["win"],
                "aggregate_plus20": aggregate["plus20"],
                "aggregate_minus10": aggregate["minus10"],
                "aggregate_top3_excluded_mean": aggregate["top3_excluded_mean"],
            }
            eligibility = contract["discovery_eligibility"]
            record["eligible"] = bool(
                record["n_2023"] >= eligibility["minimum_2023_n"]
                and record["n_2024"] >= eligibility["minimum_2024_n"]
                and record["aggregate_mean"] > eligibility["aggregate_mean_gt"]
                and record["aggregate_top3_excluded_mean"] > eligibility["aggregate_top3_excluded_mean_gt"]
            )
            records.append(record)
            identities[candidate_id] = set(zip(chosen["date"].dt.strftime("%Y-%m-%d"), chosen["symbol"]))
            selected_rows[candidate_id] = chosen

    eligible = [record for record in records if record["eligible"]]
    family_winners = []
    for family in contract["families"]:
        candidates = sorted([record for record in eligible if record["family"] == family], key=order_key)
        if candidates:
            family_winners.append(candidates[0])
    finalists = []
    max_jaccard = contract["finalists"]["maximum_pairwise_identity_jaccard"]
    for candidate in sorted(family_winners, key=order_key):
        candidate_ids = identities[candidate["candidate_id"]]
        if all(
            len(candidate_ids & identities[other["candidate_id"]])
            / len(candidate_ids | identities[other["candidate_id"]])
            <= max_jaccard
            for other in finalists
        ):
            finalists.append(candidate)
        if len(finalists) == contract["finalists"]["maximum"]:
            break

    args.output_dir.mkdir(parents=True, exist_ok=True)
    all_path = args.output_dir / "discovery_all_candidates.csv"
    pd.DataFrame(records).sort_values(["family", "candidate_id"]).to_csv(
        all_path, index=False, lineterminator="\n", float_format="%.17g"
    )
    identity_frames = []
    for rank_number, candidate in enumerate(finalists, start=1):
        chosen = selected_rows[candidate["candidate_id"]][["date", "symbol", "score", "tail_cdf"]].copy()
        chosen.insert(0, "finalist_rank", rank_number)
        chosen.insert(1, "candidate_id", candidate["candidate_id"])
        identity_frames.append(chosen)
    identity_path = args.output_dir / "frozen_finalist_discovery_identities.csv"
    frozen_rows = pd.concat(identity_frames, ignore_index=True) if identity_frames else pd.DataFrame()
    frozen_rows.to_csv(identity_path, index=False, lineterminator="\n", date_format="%Y-%m-%d", float_format="%.17g")
    result = {
        "identity": contract["identity"],
        "status": "FINALISTS_FROZEN_BEFORE_2025_HOLDOUT",
        "prereg_sha256": sha256(args.prereg),
        "tail_sha256": sha256(args.tail_cache),
        "discovery_years": [2023, 2024],
        "holdout_opened": False,
        "family_winners": family_winners,
        "finalists": finalists,
        "outputs": {
            all_path.name: sha256(all_path),
            identity_path.name: sha256(identity_path),
        },
    }
    result_path = args.output_dir / "FROZEN_FINALISTS_BEFORE_2025.json"
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"family_winners": [x["candidate_id"] for x in family_winners], "finalists": [x["candidate_id"] for x in finalists]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
