# Experiment ledger addendum — Causal 4H V1/V2 — 2026-09-13

This addendum is part of the batch02 experiment record and must be merged into `EXPERIMENT_LEDGER.md` when a full-file append path is available. No production edits.

## CAUSAL-4H-SCORING-V1-20260913 — INVALID_CAUSAL_LABEL_MATURITY

- Frozen features/models/ranks/TopN/gates were registered before the canonical 2025 labels were opened.
- Exact canonical daily input hash matched the preregistered SHA-256 `6adfb626bc1e067e662e4dc9902c6a9e3743c08a2e2ed1e6b79094307b107ba0`; no external price fetch was used.
- 2025 candidate rows after the frozen prior-day price/liquidity gate: 398,772; endpoint-resolved 398,772.
- First V1 readout used 191,901 H1 signal-date training rows and 206,871 H2 validation rows. Every Core and Monster Top1/2/3/5 policy failed its locked gates; chosen TopN was null for both heads.
- **Invalidation:** V1 admitted late-June training signals whose fifth-session close label matured on/after 2025-07-01. A model evaluated from the 2025-07-01 validation start could not causally know those labels. Signal-date split alone was insufficient.
- V1 outcomes were not used to alter features, model parameters, costs, rank rules, TopN values, cooldown, or promotion gates.
- V1 result JSON local SHA-256: `d729abe51eab1f31bf0d7a210599de74a134d955774bb539c45e74de44b9312a`.
- Decision: `INVALID_CAUSAL_LABEL_MATURITY`; do not use V1 for promotion or tuning.

## CAUSAL-4H-SCORING-V2-MATURE-LABEL-20260913 — REJECT / NO_PROMOTION

- Correction was preregistered in `CAUSAL_4H_SCORING_V2_MATURE_LABEL_SPEC.json` **before V2 outcomes were opened**.
- Only change from V1: training row requires `exit_date < 2025-07-01`. Everything else remained frozen.
- Causal maturity guard added in `causal_label_maturity.py` with focused tests in `test_causal_label_maturity.py`.
- Mature training rows: 183,925; targets: positive 91,494; +20% 2,622; <=-10% 7,962. Locked H2 validation rows: 206,871, all endpoint-resolved.
- Core, 0.5% cost: Top1/2/3/5 net means **-1.47/-1.42/-1.09/-0.46%**; medians -0.78/-0.94/-0.71/-0.50%; wins 38.71/37.90/38.71/42.02%. Every locked gate failed; chosen TopN `null`.
- Monster, 0.5% cost: Top1/2/3/5 net means **-4.30/-2.81/-1.93/-0.61%**; +20% rates 6.85/7.86/7.39/7.66%; <=-10% rates 40.73/31.65/26.21/20.65%. Every locked gate failed; chosen TopN `null`.
- Current-bin >=5,000-share sensitivity did not rescue the primary policies and was not permitted to change policy choice.
- Report: `reports/causal_4h_scoring_v2_2025_validation.md`.
- V2 result summary local SHA-256: `4ee183b802a3b6ba361a555f0107ed8fd93f1d5121c97e50d91c1ad3890e940b`.
- Historical 2026 outcomes opened by this run: **false**.
- Strict daily path/actionability remains a separate pending diagnostic; an uncomputed value must not be represented as zero. Endpoint promotion gates already fail independently.
- Decision: `REJECT_NO_PROMOTION`. Do not micro-tune the seven frozen features or thresholds against 2025H2.
- Interpretation: the causal raw-4H data pipeline remains viable, but the **seven-feature + global linear LogisticRegression ranking architecture is not competitive**. Next hypothesis must be architectural/nonlinear or regime-aware while retaining causal 4H inputs and preregistered right-tail/loss-control objectives.
- Production modified: false.
