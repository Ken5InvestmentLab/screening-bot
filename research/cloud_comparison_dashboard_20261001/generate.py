"""Render the audited aggregate CSVs as a portable, offline research dashboard."""
from __future__ import annotations

import csv
import hashlib
import itertools
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CAP = ROOT / "research/cloud_cap_comparison_20261001"
EXIT = ROOT / "research/comparisons/cloud_exit_20261001"
ARMS = ["cap1000", "cap1500", "cap2000", "cap3000", "cap5000", "nocap"]
MODES = {
    "all_conditions_unique": "銘柄均等",
    "all_conditions_stacked": "モード別積上げ",
    "volr20_low": "Silence",
    "body_pct_low": "Dive",
    "mean_rank_volr20_body_pct": "Shadow",
    "dual_top1_agreement": "Fusion",
    "dual_top1_agreement_g3_no_acute_selloff": "Balance",
}
PERIODS = ["ALL_DESCRIPTIVE", "DEV_2023_2024", "2023", "2024", "2025", "2026"]
ENDPOINTS = [f"d{day}_{side}" for day in range(1, 11) for side in ("open", "close")]


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def number(value: str, multiplier: float = 1) -> float | None:
    result = float(value) * multiplier if value else float("nan")
    return result if math.isfinite(result) else None


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def text_sha(path: Path) -> str:
    """Keep aggregate fingerprints stable across Git's Windows newline conversion."""
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def build_data() -> dict:
    cap_audit = json.loads((CAP / "independent_result_audit.json").read_text(encoding="utf-8"))
    exit_audit = json.loads((EXIT / "independent_audit.json").read_text(encoding="utf-8"))
    if cap_audit["status"] != "passed" or exit_audit["status"] != "PASS":
        raise ValueError("Only independently audited results may be rendered")
    cap_rows = read_csv(CAP / "metrics.csv")
    exit_rows = read_csv(EXIT / "metrics.csv")
    joint = read_csv(EXIT / "joint_cap_exit_dev_fixed.csv")
    cap_grid = [(int(r["cap"]), r["selector"], r["period"]) for r in cap_rows]
    expected_caps = set(itertools.product([1000, 1500, 2000, 3000, 5000, 0], MODES, ["ALL", "2023", "2024", "2025", "2026"]))
    exit_grid = [(r["arm"], r["selector"], r["period"], r["endpoint"]) for r in exit_rows]
    expected_exits = set(itertools.product(ARMS, MODES, PERIODS, ENDPOINTS))
    if len(cap_grid) != 210 or set(cap_grid) != expected_caps:
        raise ValueError("Incomplete or duplicate cap metric grid")
    if len(exit_grid) != 5040 or set(exit_grid) != expected_exits:
        raise ValueError("Incomplete or duplicate exit metric grid")
    joint_keys = [(r["selector"], r["period"]) for r in joint]
    if len(joint_keys) != 42 or set(joint_keys) != set(itertools.product(MODES, PERIODS)):
        raise ValueError("Incomplete fixed-policy grid")
    cap_data = []
    for r in cap_rows:
        cap_data.append(["nocap" if int(r["cap"]) == 0 else f"cap{r['cap']}", r["selector"], r["period"],
                         int(r["n"]), int(r["pending"]), *[number(r[k], 100) for k in
                         ("mean", "median", "win_rate", "loss10_rate", "mean_excluding_top3", "worst")],
                         number(r["one_hundred_share_total_pl_yen"]), number(r["required_capital_yen"])])
    exit_data = []
    for r in exit_rows:
        exit_data.append([r["arm"], r["selector"], r["period"], r["endpoint"], int(r["n"]),
                          *[number(r[k]) for k in ("mean_pct", "median_pct", "win_pct", "loss10_pct",
                             "top3_ex_mean_pct", "max_down_pct", "cash_pl_100_yen", "entry_capital_sum_yen")],
                          int(r["flat_count"]), number(r["nonflat_win_pct"])])
    # Equal cohorts across all 20 endpoints within each arm/mode/period.
    for group in itertools.product(ARMS, MODES, PERIODS):
        selected = [r for r in exit_data if tuple(r[:3]) == group]
        if len({r[4] for r in selected}) != 1 or len({r[12] for r in selected}) != 1:
            raise ValueError(f"Mixed exit cohort: {group}")
    # Percentage conversion and the separate cohorts must stay distinguishable.
    cap_control = next(r for r in cap_data if r[:3] == ["nocap", "all_conditions_unique", "ALL"])
    exit_control = next(r for r in exit_data if r[:4] == ["nocap", "all_conditions_unique", "ALL_DESCRIPTIVE", "d5_close"])
    if cap_control[3] != 472 or exit_control[4] != 471 or not 1.57 < cap_control[5] < 1.59 or not 1.52 < exit_control[5] < 1.54:
        raise ValueError("Unexpected normalized units or cohort baseline")
    for r in joint:
        candidates = [e for e in exit_data if e[1] == r["selector"] and e[2] == "DEV_2023_2024"]
        chosen = next(e for e in candidates if e[0] == r["dev_fixed_arm"] and e[3] == r["dev_fixed_endpoint"])
        if abs(chosen[5] - max(e[5] for e in candidates)) > 1e-9:
            raise ValueError("Fixed policy does not come from DEV only")
    metadata = json.loads((EXIT / "metadata.json").read_text(encoding="utf-8"))
    production_path = HERE / "production_reference.json"
    production = json.loads(production_path.read_text(encoding="utf-8"))
    if production["status"] != "PASS" or sha(HERE / "production_public_snapshot.json") != production["public_snapshot_sha256"]:
        raise ValueError("Production reference is not a verified frozen snapshot")
    sources = [CAP / "metrics.csv", CAP / "independent_result_audit.json", EXIT / "metrics.csv",
               EXIT / "joint_cap_exit_dev_fixed.csv", EXIT / "metadata.json", EXIT / "independent_audit.json",
               production_path, HERE / "production_public_snapshot.json"]
    return {
        "arms": ARMS, "modes": MODES, "periods": PERIODS, "endpoints": ENDPOINTS,
        "capColumns": ["arm", "mode", "period", "n", "pending", "mean", "median", "win", "loss", "top3", "worst", "cash", "capital"],
        "exitColumns": ["arm", "mode", "period", "endpoint", "n", "mean", "median", "win", "loss", "top3", "worst", "cash", "entryTotal", "flat", "nonflatWin"],
        "caps": cap_data, "exits": exit_data, "joint": joint, "production": production,
        "sourceCutoff": metadata["source_cutoff"], "dailySha256": metadata["daily_sha256"],
        "actionsSha256": metadata["actions_sha256"],
        "sources": [{"path": p.relative_to(ROOT).as_posix(), "sha256": text_sha(p)} for p in sources],
        "sourceHashBasis": "file bytes with CRLF normalized to LF",
    }


def main() -> None:
    data = build_data()
    encoded = json.dumps(data, ensure_ascii=False, separators=(",", ":"), allow_nan=False).replace("<", "\\u003c")
    template = (HERE / "template.html").read_text(encoding="utf-8")
    for key, value in {"@@STYLE@@": (HERE / "style.css").read_text(encoding="utf-8"), "@@DATA@@": encoded,
                       "@@SCRIPT@@": (HERE / "dashboard.js").read_text(encoding="utf-8")}.items():
        template = template.replace(key, value)
    output = HERE / "index.html"
    output.write_text(template, encoding="utf-8", newline="\n")
    manifest = {"status": "PASS", "cap_metrics": len(data["caps"]), "exit_metrics": len(data["exits"]),
                "fixed_policy_rows": len(data["joint"]), "sources": data["sources"],
                "source_hash_basis": data["sourceHashBasis"],
                "renderer_sources": {p.name: sha(p) for p in [HERE / "generate.py", HERE / "template.html", HERE / "style.css", HERE / "dashboard.js"]},
                "index_sha256": sha(output), "checks": ["independent audit receipts", "complete unique grids", "percentage units",
                "separate cap and exit cohorts", "equal twenty-endpoint cohorts", "DEV-only fixed policies"],
                "no_model_execution": True, "no_production_mutations": True}
    (HERE / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"PASS: {len(data['caps'])} cap / {len(data['exits'])} exit metrics; {output.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
