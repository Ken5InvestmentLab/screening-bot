# V16 backward candidate admissibility receipt — 2026-09-18

CANDIDATE_ADMISSIBILITY=GO
SCOPE=REFERENCE_FAMILY_ONLY_NOT_PRIMARY
DECISION_BASIS=CANONICAL_REPRODUCIBILITY_ONLY

## 2022 canonical anchor
- workflow run: 34605714116
- workflow path: `.github/workflows/tvfree-v16-backward-2022-test.yml`
- artifact: 10266990667 `tvfree-v16-backward-2022-34605714116`
- artifact digest: `sha256:8254745a3508742de49339e6460a095a51c0a904442bb7f9cf3636da1aaa012e`
- head/source commit: `bcc2b9f1ce2a2b8ce6bc02e21be72c48899690d5`
- fixed daily corpus artifact: 10264205130 (declared by `tvfree_screener/RUN_V16_2022`; downloaded by the workflow from preserved run 34599959356)
- endpoint audit: Supervisor-confirmed 31/31 next-XTKS-open / fifth-XTKS-close / return match, missing endpoint=0.
- identity guard: n=31 is NOT primary 2022 volr20 n=23 and must never be merged into primary.

## Frozen generator/spec provenance at head SHA
- `tvfree_screener/v16_backward_2022.py` blob SHA: `159994c571403f7c349dded7a3851a5d9338a479`
- `tvfree_screener/v16_pre2025_volr20_rank.py` is present at the same head SHA and defines the frozen selection function: V7 extreme Tail (`cdf>=0.999`), `med_ret5<=0`, same-day `volr20` ascending, `tail_cdf/tail_p` descending tie-break, one-business-day same-symbol cooldown.
- `tvfree_screener/v9_conditional_quality_research.py` blob SHA: `45a1272fe49c526bbf69956419e34e96d696f7d6`; its `generate_tail_pool(q,start,end)` is date-parameterized and causal by month.
- `v16_backward_2022.py` demonstrates the exact composition used for 2022: fixed daily OHLCV -> `v9.prepare(raw)` -> `v9.generate_tail_pool(...)` -> `v16.select(tail,trading_dates)`.

## Cross-year admissibility
The generator building blocks and selection spec are frozen at one source commit, and the preserved daily corpus is a fixed input provenance. Therefore the same composition can be applied to 2023, 2024 and 2025 without candidate-name discovery or rule tuning. Cross-year performance is NOT part of this GO decision.

NEXT_ACTION=GENERATE_2023_ROWS_WITH_SAME_HEAD_SHA_AND_FIXED_DAILY_CORPUS

## Guards
- Do not use 2026.
- Do not resume strict_3pt exploration.
- Do not change production or main.
- Do not select/reject this family by performance.
