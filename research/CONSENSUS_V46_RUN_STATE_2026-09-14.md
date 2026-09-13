# Consensus V46 run state — 2026-09-14

## Triggered audit
- Experiment: outcome-free V46 point-in-time split eligibility audit
- Branch: `research/consensus-atr-regime-gate`
- Trigger marker: `research/RUN_V46_PIT_SPLIT_ELIGIBILITY`
- Trigger commit: `040bc01f26d378e076a377161c76cbea0fc23744`
- GitHub Actions run: `34775030470`
- Workflow: `.github/workflows/no-tv-consensus-v46.yml`
- State at record time: `in_progress`

## Frozen interpretation rules
- V46 is an outcome-free data-contract audit; strategy returns must not be used to choose a price cap, ATR rule, family, threshold, or model.
- The old adjusted `prior-close <= 1000` rule is not mandatory for the future system.
- V47 clean PIT comparison remains exactly two price-policy arms: `NOCAP` and `CAP1000_PIT`.
- Do not grid-search alternate caps such as 500/1500/2000 on this first clean comparison.
- Do not treat deleting contaminated rows from the old scored sample as a clean rebuild.
- V47 must rebuild eligibility/training/scoring under PIT semantics before comparing the two arms.
- Canonical target remains next XTKS open -> D+5 close.
- 2026 outcomes remain report/robustness-only.
- Production/main/Discord/Spreadsheet/Stable★6/Sniper/Mega/TradingView/watchlist-builder/updater remain untouched.

## Next action after V46 completes
1. Inspect artifact and `SHA256SUMS.txt` before using any audit counts.
2. Confirm split-event artifact provenance/hash and outcome-free adjusted-only vs PIT-only membership differences.
3. If the audit is valid, proceed to a clean V47 rebuild with identical model architecture and exactly `NOCAP` vs `CAP1000_PIT`.
4. If V46 fails data/contract checks, fix only the audit/data plumbing; do not tune strategy logic from the failed run.
