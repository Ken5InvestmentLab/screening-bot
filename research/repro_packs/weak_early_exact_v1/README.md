# WEAK_EARLY_EXACT_V1 REPRO_PACK

Status: **EXACT_REPRODUCED** for the preserved 2023-2025 legacy rank comparison. Research-only; 2026 remains SEALED.

## Exact command

From the repository root, after downloading the two non-expired GitHub Actions artifacts:

```powershell
gh run download 34599959356 --repo Ken5InvestmentLab/screening-bot --name tvfree-frozen-dataset-run80-preserved --dir .cache/recovery/artifact_10264205130
gh run download 34600083474 --repo Ken5InvestmentLab/screening-bot --name tvfree-v7-causal-tail-cache-2023-2025 --dir .cache/recovery/artifact_10264251140
py research/repro_packs/weak_early_exact_v1/reproduce.py --tail-cache .cache/recovery/artifact_10264251140/v7_causal_tail_cache_2023_2025.csv --daily-corpus .cache/recovery/artifact_10264205130/tse_daily.csv --output-dir research/repro_packs/weak_early_exact_v1/output
```

The reproducer refuses input SHA drift, unresolved top ties, endpoint-price drift, row-count drift, and historical metric drift.

## A-H handoff receipt

1. Identity is `WEAK_EARLY_EXACT_V1`; it is a legacy research replay, not a production candidate.
2. Population is the preserved causal V7 Tail artifact, already filtered at `tail_cdf >= 0.999`.
3. Monthly V7 training used only labels with `target_end_date < month_start` and required at least 30,000 rows.
4. Fixed gate is `med_ret5 <= 0 AND ret10 <= 0.5735294117647058`.
5. Selection is one candidate per signal date; the three exact rankers are volr20 LOW, body_pct LOW, and their mean percentile rank.
6. Rank direction is ascending; contemporaneous tie-break is `tail_cdf` descending. No selected day remains tied after it.
7. Legacy rank-comparison cooldown is **none**; adding a prior-session same-symbol cooldown breaks n=128 and is a later separate variant.
8. Source commit for the preserved cache build is `ef8754d835ccb39faf783092f969417a3ea74ce9`.
9. V7/V9 source blobs are `f7f49ab2e09496494adfb365c94e969973c4070c` and `45a1272fe49c526bbf69956419e34e96d696f7d6`.
10. Tail input is artifact `10264251140`, file SHA-256 `0398969e13cc4b79f64cf8ad3b300ab34c0270ac70d20367994979478b60849d`.
11. Daily input is artifact `10264205130`, file SHA-256 `6adfb626bc1e067e662e4dc9902c6a9e3743c08a2e2ed1e6b79094307b107ba0`.
12. Endpoint is signal T, next official XTKS session open, fifth official XTKS session close; cost 0%; win is gross > 0.
13. Each output CSV includes signal date, symbol, candidate identity, entry/exit dates and prices, gross return, and 100-share P/L.
14. `metrics.json` reports every year and aggregate; `manifest.json` pins all output content hashes.
15. 2023-2024 exact headline n=128 and all three recorded means/medians/tail metrics reproduce to floating precision.
16. 2025 exact n=44 and recorded means reproduce; 2026 is neither read nor generated.
17. Production/main, workflows, Discord, Sheets, Stable, Sniper, Mega, TradingView, and watchlists are untouched.

## 2022 boundary

The exact identity above covers the preserved 2023-2025 Tail artifact. Applying the frozen generator and gate to 2022 is runtime-sensitive and does not reproduce the historical 89/29/23 summary. The two unmodified fixed-spec results are preserved in `2022_runtime_sensitivity/`; do not select or retune either result by closeness to that summary.
