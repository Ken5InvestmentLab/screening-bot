# TV-Free replacement readiness — 2026-09-18

Status: **RECOVERY COMPLETE / FORWARD_SHADOW READY / PRODUCTION NO-GO / FIXED-CANDIDATE 2026 REPORTING OPEN / META 2026 SEALED**

Update: explicit user authorization subsequently opened 2026 for the already-frozen five Weak+Early candidates and the exact-recovered Cloud Monster on a reporting-only basis. Meta and unrelated 2026 lanes remain sealed. Exact Weak+Early 2023-2026 descriptive ranking is mean-rank, DUAL+G3, body_pct LOW, DUAL, volr20 LOW. The 2026-year descriptive six-candidate ranking is mean-rank, body_pct LOW, Cloud Monster canonical, DUAL+G3, DUAL, volr20 LOW; Cloud and Weak+Early observation months differ, so this is not a promotion verdict.

## Objective

TradingView signal dependencyを外し、現行production scoringと同一のcanonical endpointで正面比較できる独立システムを作る。比較前に候補生成ルールを固定し、2026 outcomeでselector、threshold、gateを選び直さない。

## What is now executable

- Exact historical identity: `WEAK_EARLY_EXACT_V1`。
- Input: causal monthly V7 Tail population。
- Fixed candidate gate: `med_ret5 <= 0 AND ret10 <= 0.5735294117647058`。
- Five frozen selectors: volr20 LOW, body_pct LOW, mean-rank, DUAL_TOP1_AGREEMENT, DUAL+G3 (`med_ret1 >= -0.01`)。
- Historical endpoint: signal T -> next official XTKS open -> fifth official XTKS close, cost 0%, win = gross > 0。
- Candidate-only entrypoint: `research/repro_packs/weak_early_exact_v1/select_shadow_candidates.py`。
- The entrypoint reads signal-time fields only and reproduces all five historical candidate identities exactly; no target, entry, exit, or realized-return column is read.
- `CLOUD_MONSTER_LEGACY_EXACT_V1` is now reproduced from Actions artifact `10266329903` through all four recovered source stages with 63/63 identities and zero close/return drift.
- `CLOUD_MONSTER_CANONICAL_NEXT_OPEN_FIFTH_CLOSE_V1` fixes those same 63 signals to the common next-open→fifth-close endpoint; canonical rows and metrics are hash-pinned under `research/repro_packs/cloud_monster_legacy_exact_v1/output/canonical_next_open_fifth_close/`.
- `CLOUD_MONSTER_FROZEN_SHADOW_MODEL_V1` freezes the exact imputer/scaler/logit/threshold and exposes an outcome-blind scorer. Historical causal candidate identity is 64 rows: all 63 evaluated legacy rows plus one row previously removed only by endpoint-availability (`ret5.notna`).

## Frozen historical position

| Selector | 2023-2025 n | Mean | Median | Win | Top3-ex |
|---|---:|---:|---:|---:|---:|
| volr20 LOW | 172 | +6.33% | +1.06% | 51.74% | +4.38% |
| body_pct LOW | 172 | +6.54% | +0.99% | 50.58% | +4.60% |
| mean-rank | 172 | +6.89% | +1.45% | 52.33% | +4.95% |
| DUAL_TOP1_AGREEMENT | 140 | +7.17% | +1.25% | 52.14% | +4.79% |
| DUAL + G3 | 117 | +7.98% | +1.74% | 53.85% | +5.14% |

These values are exact for the preserved 2023-2025 artifact. They are **not yet an apples-to-apples victory over current production scoring**, because production and Weak+Early do not share the same signal population or historical availability contract.

## Remaining bridge to a fair current-logic comparison

1. Run the pinned monthly causal Tail generator on an independently maintained daily corpus without TradingView alerts.
2. Feed each completed monthly Tail pool to the outcome-blind shadow selector and timestamp/hash its candidate ledger before any endpoint matures.
3. Record current production candidates separately without changing their logic, alerts, or workflow.
4. After fifth-session endpoints mature, evaluate both ledgers with the same calendar, endpoint, cost, and missing-price policy.
5. Treat 2026 only as sealed reporting/robustness evidence. Do not use it to pick among the five already-opened selectors or to retune any threshold.
6. Require a preregistered minimum sample and comparison gate before any production proposal. Until that separate contract is committed, status stays `FORWARD_SHADOW_ONLY`.

## Known blockers and risks

- 2022 historical 89/29/23 identity is not exact-recovered; unchanged generator executions are runtime-sensitive and the frozen 2022 DUAL+G3 summary was weak.
- The monthly V7 model artifact/runtime for future generation must be container- or lockfile-pinned before forward candidate identity can be called deterministic across hosts.
- Cloud Monster legacy is exact-recovered, but its historical model was developed on 2026 outcomes. It is valid forensic/reference evidence and may be frozen for strictly prospective shadowing; its 2026 in-sample/development performance cannot be used as promotion evidence.
- DUAL+G3 is the strongest preserved 2023-2025 selector, but it is a shadow challenger, not a production promotion.

## Production boundary

No main, production code, workflow, Discord, Spreadsheet, Stable, Sniper, Mega, TradingView, or watchlist component is changed by this work.
