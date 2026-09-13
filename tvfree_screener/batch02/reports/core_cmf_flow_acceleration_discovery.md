# CMF Flow Acceleration — discovery

**Decision: REJECT_CMF_FLOW_ACCELERATION.** This is retrospective discovery, not untouched OOS. The frozen candidate/rank/selection digests reproduced exactly before outcomes were opened. Only 2022H2 and 2023 were evaluated; 2024+ outcomes remained closed.

Target: next official XTKS session open to the close of the fifth session including entry. Primary cost is an assumed 0.5% round trip; it is not measured live cost. Selection allowed up to five names per day and one official-session same-symbol cooldown.

| Period | Selected / resolved | Mean | Median | Win | +10 / +20 / +50 | -10 / -20 | Top1 excl. mean | Top3 excl. mean | Label coverage |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2022H2 | 595 / 587 | -0.934% | -0.836% | 32.8% | 1.5 / 0 / 0% | 2.7 / 0% | -0.966% | -1.023% | 98.7% |
| 2023 | 1,205 / 1,181 | -0.286% | -0.713% | 33.8% | 2.0 / 0.85 / 0.34% | 1.6 / 0.17% | -0.413% | -0.567% | 98.0% |

All returns above are after the assumed 0.5% round-trip cost. At zero assumed cost, mean return was still -0.434% in 2022H2 and only +0.214% in 2023; medians remained negative. The frozen positive mean/median/win/Top3-exclusion gate failed in both periods. Positive monthly mean share was 0/6 and 3/12. Complete-day cohort means were -0.920% and -0.269%; their weekly-block bootstrap 95% mean intervals were [-1.407%, -0.470%] and [-0.803%, +0.403%]. Top-five symbol shares were 5.11% and 4.06%, so performance was not carried by one symbol.

| Period | Unresolved selected labels |
|---|---|
| 2022H2 | 5 zero-volume holding sessions; 2 missing canonical label rows; 1 entry zero/unknown volume |
| 2023 | 11 zero-volume holding sessions; 11 missing canonical label rows; 2 entry zero/unknown volume |

The unresolved 32 of 1,800 selected rows remain outside return metrics, not imputed or shifted. The missing canonical rows do not prove a missing market bar; source coverage needs separate verification. Therefore these are resolved-subset metrics, not an exact all-selected result. Even at 98% coverage the candidate fails multiple preregistered gates; do not tune or open 2024 to rescue it. Full metrics and exact gate values are in the JSON report.
