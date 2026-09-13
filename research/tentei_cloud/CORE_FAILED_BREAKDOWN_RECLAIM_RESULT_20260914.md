# Core Failed-Breakdown Reclaim preconfirmation — 2026-09-14

Research-only. Production unchanged. Locked 2025H2 confirmation and all 2026 outcomes remain unopened.

## Integrity correction

The first workflow run `34768879678` is invalid and its performance must not be used. Its evaluator incorrectly derived previous-day low/close/volume by aggregating raw Yahoo 1H instead of using the frozen previous completed XTKS daily bar required by the preregistered spec.

The corrected authoritative preconfirmation is:

- run: **34768985489**
- artifact: **10321840445**
- artifact digest: `sha256:1abdc3aa3ebdf188bbe532100000c50a968f285437f7792fb68bd8384f3d95d8f`
- trigger commit: `95d296ecb5429e3e45046684fc2c5f9e668f2b51`
- raw 1H source run: **34592896202**
- canonical daily source run: **34599959356**
- canonical daily SHA-256: `6adfb626bc1e067e662e4dc9902c6a9e3743c08a2e2ed1e6b79094307b107ba0`
- corrected contract-test run: **34768958344**, success.

The corrected evaluator:
- uses the frozen canonical prior completed daily low/close/volume;
- reconstructs 13:00-split session bars from the frozen raw 1H source;
- selects every event satisfying the zero-free-parameter reclaim rule;
- applies the frozen 5-XTKS-session same-symbol cooldown;
- evaluates next official XTKS session open -> signal date + fifth official-session close;
- opens DEVELOPMENT and INTERNAL_VALIDATION only.

## Frozen candidate rule

An eligible session is selected when all are true:
1. candidate session low < previous completed daily low;
2. candidate session close > previous completed daily low;
3. candidate session close > candidate session open;
4. prior daily close <= 1,000 JPY;
5. prior daily volume >= 10,000 shares;
6. candidate session volume >= 5,000 shares.

No rank, Top-N, backfill, threshold sweep, or post-hoc filter exists.

## DEVELOPMENT — 2024-11-01 through 2025-03-31

Resolved: **5,252 / 5,252**.

At the frozen 0.5% round-trip cost:
- mean: **-0.766%**
- median: **-0.832%**
- win rate: **41.09%**
- gross >=+10%: 4.00%
- gross >=+20%: 0.86%
- gross <=-10%: 4.11%
- Top1-removed mean: **-0.778%**
- Top3-removed mean: **-0.802%**

Frozen gate:
- min n: PASS
- mean >0: **FAIL**
- median >=0: **FAIL**
- win >50%: **FAIL**
- Top3-removed mean >0: **FAIL**
- loss10 <=10%: PASS

**DEVELOPMENT FAIL.**

Even at zero assumed cost:
- mean -0.266%
- median -0.332%
- win 44.94%
- Top3-removed mean -0.302%

So the failure is not caused only by the 0.5% cost assumption.

## INTERNAL_VALIDATION — 2025-04-01 through 2025-06-30

Resolved: **3,285 / 3,285**.

At 0.5% cost:
- mean: **+0.331%**
- median: **-0.185%**
- win rate: **48.13%**
- gross >=+10%: 6.85%
- gross >=+20%: 1.55%
- gross <=-10%: 3.74%
- Top1-removed mean: +0.314%
- Top3-removed mean: +0.283%

Frozen gate:
- min n: PASS
- mean >0: PASS
- median >=0: **FAIL**
- win >50%: **FAIL**
- Top3-removed mean >0: PASS
- loss10 <=10%: PASS

**INTERNAL_VALIDATION FAIL.**

## Frozen decision

The preregistration requires **both** preconfirmation blocks to pass every gate.

Observed:
- DEVELOPMENT: FAIL
- INTERNAL_VALIDATION: FAIL
- preconfirmation_pass: **false**
- locked_confirmation_opened: **false**

Therefore:

**REJECT FAILED-BREAKDOWN RECLAIM. DO NOT OPEN 2025H2.**

No threshold, candidate rule, cooldown, cost, session split, or ranking may be retuned from these opened outcomes.

This result closes the currently preregistered Failed-Breakdown Reclaim Core family. A future Core experiment, if any, must be a genuinely different low-DOF mechanism preregistered before outcomes.

2026 outcomes opened: false.
Production modified: false.
