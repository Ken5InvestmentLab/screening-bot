# Automation Findings

## 2026-09-12 — fixed early-maturity veto cross-check on reproducible V16

Safety: research-only. No production writes. Current Stable/Sniper/Mega are benchmarks only and are not components of the new TV-Free system.

Goal: before applying the previously fixed `ret10 <= 0.5735294117647058` early-maturity veto to V29 Three-head Consensus, check whether the same fixed veto improves another reproducible pre-2026 Monster family without changing the threshold.

Source: V16 artifact from run `34603792445`, artifact `10265428076`. V16 already includes the weak-market gate `med_ret5 <= 0`; therefore this test isolates the added early-maturity veto.

### 2025 pooled
V16 baseline: n70, mean +1.30%, median -9.25%, win 34.3%, >=10% 22.9%, >=20% 14.3%, >=50% 10.0%, <=-10% 42.9%, top-1-removed -0.56%, top-3-removed -3.54%.

With fixed early-maturity veto: n31, mean +3.85%, median -7.29%, win 41.9%, >=10% 29.0%, >=20% 12.9%, >=50% 6.45%, <=-10% 38.7%, top-1-removed -0.36%, top-3-removed -4.50%.

### 2025H1
Baseline: n37, mean +0.52%, win 32.4%, <=-10% 35.1%.
With veto: n15, mean -2.12%, win 40.0%, <=-10% 33.3%.

### 2025H2
Baseline: n33, mean +2.19%, win 36.4%, <=-10% 51.5%, top-1-removed -1.81%.
With veto: n16, mean +9.45%, win 43.8%, <=-10% 43.8%, top-1-removed +1.41%.

### 2026 reporting-only
Baseline: n58, mean +3.88%, median -2.40%, win 43.1%, >=20% 20.7%, <=-10% 36.2%, top-1-removed +1.89%, top-3-removed -1.15%.
With veto: n27, mean +0.47%, median -2.89%, win 40.7%, >=20% 14.8%, <=-10% 33.3%, top-1-removed -0.76%, top-3-removed -3.07%.

Decision: **do not generalize the early-maturity veto across Monster families.** It helps V16 materially in 2025H2 but hurts 2025H1 and 2026. The earlier Cloud Monster improvement therefore appears architecture-dependent. Apply the fixed two-gate structure to V29 only as an independent hypothesis test; do not promote it unless pre-2026/purge-safe V29 results improve across multiple temporal blocks.

Current blocker: the raw V29 `fixed_min98_both` pick file/artifact was not found in the accessible GitHub branch or ChatGPT Library during this run; only the preserved headline result is available. Next run should continue artifact/commit forensics for V29 raw picks, and if recovered run the exact fixed two-gate test without threshold changes.

Core direction remains separate: direct 1H Core translation was rejected; keep Core anchored to 4H/session + daily context and research a lower-downside TV-Free Core independently of Monster.
