# Consensus V47 midterm H1 diagnostic result — 2026-09-14

Label: `MIDTERM_DIAGNOSTIC_NOT_PROMOTION_EVIDENCE`

This is not formal promotion evidence. Formal raw acceptance remains failed/pending and no acceptance threshold is relaxed. The opened H1 period is no longer an untouched holdout. Same-family retuning from this result is forbidden.

## Frozen contract

- period: 2025-01-06..2025-06-30
- endpoint: next official XTKS open -> D+5 close
- transaction cost: 0%
- win: gross canonical return > 0
- architecture: V11 frozen 3-head
- consensus: min
- threshold: 0.95
- guard: none
- sessions: both
- same-symbol cooldown: strict 5 XTKS sessions
- replacement: false
- price arms: exactly NOCAP and CAP1000_PIT
- source: preserved immutable Yahoo raw seed run `34592896202`
- diagnostic workflow: `34824194221` SUCCESS
- artifact: `consensus-v47-midterm-diagnostic-34824194221`, SHA256 `c46e90cba472c291a7db068ff1dadb0959764dcef97eb006dd6c3b918779f866`

## Coverage caveat

This diagnostic uses only physically available preserved raw bars; missing pairs remain missing and were not interpolated or synthesized.

- NOCAP: 301,897 / 853,061 required pairs = **35.3898%**; monthly minimum 33.9002%; 2,592 completely missing required symbols; restored-pair coverage 0%
- CAP1000_PIT: 258,339 / 310,831 required pairs = **83.1124%**; monthly minimum 77.3420%; 642 completely missing required symbols; restored-pair coverage 0%

Therefore all performance below is coverage-bypassed partial diagnostic evidence only.

## H1 cost-0 result

| Arm | n | Mean | Median | Win | +10 | +20 | +50 | -10 | -20 | Top1-ex | Top3-ex | Unique symbols | Max symbol share |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| NOCAP | 50 | **+0.1074%** | -2.7270% | 36.00% | 16.00% | 8.00% | 0.00% | 12.00% | 2.00% | -0.7566% | -2.0148% | 26 | 12.0% |
| CAP1000_PIT | 60 | **-1.1568%** | -0.4011% | 46.67% | 13.33% | 0.00% | 0.00% | 11.67% | 3.33% | -1.4639% | -2.0601% | 36 | 10.0% |

Under the frozen price-arm chooser's primary criterion (development mean), **NOCAP is the diagnostic H1 leader**. This does not promote NOCAP because formal raw acceptance has not passed and the partial-coverage population differs materially between arms.

Both arms are weak on robust central/tail-excluded diagnostics: NOCAP has negative median and Top1/Top3-ex means, while CAP1000_PIT has negative mean, Top1-ex, and Top3-ex. No price-cap grid search or same-family retune is allowed from these opened results.

## Holdout state

- H1: opened for diagnostic; no longer untouched
- H2: unopened
- 2026: unopened for this diagnostic

## Next action

Keep formal promotion path separate. Continue the unique formal raw retry `34810592135` without duplicate triggering. For the diagnostic sequence, if H2 is opened, evaluate **only the frozen H1 leader NOCAP** under the same unchanged contract and cost 0%, and label it diagnostic-only. Do not retune parameters or reopen CAP1000_PIT H2 as a rescue path.
