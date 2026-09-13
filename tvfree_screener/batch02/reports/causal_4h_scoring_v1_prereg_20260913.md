# Causal 4H scoring v1 preregistration — 2026-09-13

This freezes the first scoring experiment **before canonical endpoint labels are opened/joined**.

## Fixed architecture

The already-frozen seven causal intraday features are used unchanged. There is no feature clipping or imputation.

Two heads are evaluated separately:

- **Core:** L2 logistic model for the probability that 5BD gross return is positive. A separate fixed loss head estimates probability of <= -10% and is only a ranking tie-break.
- **Monster:** L2 logistic model for the probability of >= +20% 5BD. The same loss head is the tie-break.

Both models use RobustScaler fitted on training rows only and fixed LogisticRegression parameters (`C=1`, `lbfgs`, balanced classes, max_iter 1000).

There is deliberately no arbitrary weighted blend between Core and Monster.

## Time split

- 2024-09-17–2024-12-31: context/warmup only
- 2025-01-01–2025-06-30: training
- 2025-07-01–2025-12-31: locked validation and TopN policy choice
- 2026-01-01–2026-09-10: report-only; no tuning
- post-freeze future: prospective shadow evidence

## Candidate gates

Primary:
- all seven v1 features available
- previous completed daily close <= 1,000 JPY
- previous completed daily volume >= 10,000 shares

The old 5,000-share candidate-bin threshold is reported only as a predeclared sensitivity because absolute hourly/session volume semantics remain less trustworthy. It cannot alter the primary policy choice in this experiment.

## Causal selection

AM and PM are separate live cohorts because they become available at different cutoffs. For each cohort, Top1/2/3/5 are evaluated independently. Each policy has its own five-official-session same-symbol cooldown. An AM pick blocks a later same-day PM repeat of that symbol for that same policy.

## Canonical target

Use batch02's current endpoint only:

**next official XTKS session open -> fifth official XTKS session close**, where the entry session is day 1.

Do not substitute the older research branch's candidate-close endpoint.

Preferred label source is the already-recorded cached daily panel with SHA-256 `6adfb626bc1e067e662e4dc9902c6a9e3743c08a2e2ed1e6b79094307b107ba0`. If that exact source cannot be recovered, stop this experiment and register a separate source substitution; do not silently derive labels from 1h.

## Frozen validation gates

Core must have at least 50 resolved observations, positive 0.5%-cost mean, nonnegative net median, >50% net wins, positive top3-removed net mean, and <=20% gross loss10 rate.

Monster must have at least 30 resolved observations, positive 0.5%-cost mean, >=10% gross +20% rate, positive top1-removed net mean, and <=40% gross loss10 rate.

If no TopN policy passes, the result is NO_PROMOTION. Do not micro-tune the frozen rules.
