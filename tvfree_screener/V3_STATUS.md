# TV-Free V3 research status (TEST ONLY)

## Guardrails
- Branch: `test/tvfree-screener-v1`
- Draft PR: #13
- No merge to `main` without explicit user Go approval.
- No production Discord/Spreadsheet writes.
- No production Stable★6/Sniper/Mega/TradingView changes.
- Realistic entry: next trading session open.
- 2026 has already been inspected elsewhere in this research and is not pristine; never tune to it.

## V3 Short (5BD)

Historical non-reproducible reference: 2026 Mar-Aug n=29, mean +5.42%, median +2.06%, win 65.5%, +10% 13.8%, -10% 6.9%. Exact old parameters were never committed.

### Exact-feature reconstruction
Used the same 45 `run.py` features and XGBoost shape (180 trees, depth 3, learning rate .04, min_child_weight 25, reg_lambda 5, reg_alpha .2), with causal monthly training.

2025-only Core: `r_top10 - 2*r_loss10`.
- 2025H1 mean +0.59%, median +0.58%, win 58.0%, -10% 2.5%.
- 2025H2 mean +0.94%, median +0.57%, win 58.9%, -10% 0%.

2025-only recent-outcome Meta: recent 30 Core outcomes, win >=55%, loss10 <=10%.
- 2025H1 n=48 mean +1.05%.
- 2025H2 n=76 mean +1.14%.
- frozen 2026 Mar-Aug n=26 mean -1.27%, median -0.46%, win 42.3%.
Rejected; do not retune to 2026.

Contemporaneous `med_ret5 >= -1%` gate improved frozen 2026 Core to about n=97 / mean +0.17% / -10% 1.0%, but median stayed negative. Defensive supporting observation only.

### Whole-universe Attack heads
2025-selected `r_hit20-r_loss10`, `med_ret5>=-1%`, `r_hit10>=.85`:
- 2025H1 n=102 mean +1.93%.
- 2025H2 n=106 mean +2.10%.
- frozen 2026 Mar-Aug n=97 mean +0.06%, median -0.97%, win 42.3%, -10% 7.2%.
Rejected.

### Distinct event-family Attack experiment
`short_event_experiment.py` tested 10 fixed variants across five materially different event families using 2024-2025 only. Result: **0/10 variants passed** the pre-2026 robustness gate, so no 2026 candidate was opened. Short Attack remains **none/unaccepted**.

### Reproducible Short runner
Added `v3_short_reconstruction.py` at commit `5eae93dd...` and integrated it into the test workflow at `1f0461e2...`.

It explicitly implements:
- same 45 `run.py` features,
- monthly causal 180-tree exact-shape XGBoost,
- relative top-decile next-open->5BD target head,
- -10% next-open->5BD loss head,
- prediction-day percentile normalization,
- Core `r_top10 - 2*r_loss10`,
- one-selection-day same-symbol cooldown,
- defensive supporting lane `med_ret5 >= -1%`,
- recent-outcome Meta rejected/inactive,
- Attack none/unaccepted,
- JSON/CSV research artifacts only.

Actions confirmation is pending. Until it succeeds and exact outputs are reconciled, prior Core numbers above remain research notes rather than a claim that the new runner has reproduced them exactly. If there is a discrepancy, investigate/document it rather than tuning thresholds against 2026.

## V3 Swing (10BD)
Current frozen research candidate: `v3_swing_v2.py`.
Architecture: MomCross -> causal semiannual event-quality model -> training empirical-CDF normalization -> Breadth Meta -> `score_R >= 0.20`.

Observed next-open -> 10BD:
- 2025H1 n=33 mean +2.68%, median +2.12%, win 57.6%, +10% 15.2%, -10% 6.1%.
- 2025H2 n=31 mean +1.95%, median -0.70%, win 45.2%, +10% 16.1%, -10% 6.5%.
- 2026 Mar-Aug contaminated check n=30 mean +1.42%, median +1.63%, win 60%, +10% 10%, -10% 3.3%.

Swing S remains the strongest reproducible defensive candidate. Swing A remains unaccepted.

## Current architecture decision
- Short Core: reproducible design implemented; weak research/supporting lane pending Actions confirmation.
- Short defensive market gate: supporting lane only.
- Short recent-outcome Meta: rejected.
- Short Attack: none.
- Swing S: frozen candidate.
- Swing A: none.

## Next
1. Confirm the new Short runner in GitHub Actions and reconcile its artifact with prior research notes.
2. Confirm/freeze Swing S reproducibility in Actions.
3. Generate unified comparison against Stable★6 historical reference.
4. Validate operational runtime/cost.
5. Production migration remains blocked pending explicit user Go.
