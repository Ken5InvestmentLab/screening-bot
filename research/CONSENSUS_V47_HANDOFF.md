# Consensus V47 clean PIT handoff

Updated: 2026-09-14 15:41 JST
Branch: `research/consensus-atr-regime-gate`
Scope: research-only. Production/main/Discord/Spreadsheet/Stable★6/Sniper/Mega/TradingView/watchlist-builder/updater untouched.

## Promotion boundary
Only V47 clean PIT evidence is promotion-relevant. V43/V44 returns remain non-promotion evidence because of point-in-time split/universe leakage.

## Frozen contracts
- PIT universe replay: run `34771221050` accepted.
- V46 split audit: run `34775030470` accepted.
- Price-policy arms: exactly `NOCAP` and `CAP1000_PIT`.
- Canonical target: next official XTKS open -> fifth official XTKS close.
- V11 3-head architecture / threshold 0.95 frozen for first clean comparison.
- 2026 outcomes forbidden for selection.
- PIT daily volume = frozen adjusted daily volume / cumulative future split factor.
- Prior-volume gate and daily-volume ratio technicals use PIT daily volume.
- Yahoo raw 1H volume stays unchanged for session-volume gate and session-volume ratio technicals; never divide raw 1H volume by split factor.
- Listing identity epochs isolate prelisting history from feature/target/cooldown state.
- H2 feature artifact must remain blind to return targets.

## Authoritative daily source
96ut restoration run `34798987098` recovered 251/251 historical/restored symbols and merge audit `34799650589` passed. Final V47 daily PIT materialization run `34799835035` is authoritative and passed all daily gates:
- `daily_coverage_pass=true`
- `required_coverage_pass=true`
- `restored_daily_coverage_pass=true`
- missing required symbols = 0
- missing required symbol/date pairs = 0
- strategy returns/model scores unopened.

## First raw 1H attempt
Raw freeze run `34800587082` completed GitHub-level SUCCESS across all 12 shards, but transport was Yahoo-rate-limited. An inspected shard had 0/324 successful symbols and 324/324 `http_429`. Workflow success was never treated as coverage acceptance.

Transport-only hardening for subsequent retries:
- commit `2880cc20165ef35705290330052e40d5c3ba1975`: query1/query2 alternation, persistent session, Retry-After support, bounded exponential backoff, 8 attempts, 0.55s pacing.
- contract test run `34806715208`: SUCCESS.
- commit `e61fcdfc4fb2f18eee41dde5ae79474e38b2a5be`: future raw workflow `max-parallel: 2`, timeout 180 min.

No eligibility/model/target/feature/threshold semantics changed.

## Formal raw coverage acceptance
Initial verifier run `34810149461` is **invalid as acceptance evidence** because the verifier crashed on an empty gzip shard (`pandas.errors.EmptyDataError`) before frozen coverage could be evaluated.

The verifier was fixed in commit `efc4a0c463a6246b884fd73ad0320256b6ce2949` so an empty shard contributes zero available pairs and the verifier fails closed rather than crashing. Contract test run `34810228288` passed SUCCESS.

The exact same frozen acceptance was rerun as `Consensus V47 Raw1H Coverage Acceptance` run `34810234454`; workflow conclusion SUCCESS means the receipt was emitted, not that coverage passed. Artifact digest: `sha256:83c35186addada392a3117f7f97eaca2d7b189670ceee306bb2284328c8a06c3`.

Formal receipt:
- top-level `accepted=false`
- `raw_unique_symbol_dates=0`
- `NOCAP`: required 853,061; present 0; missing 853,061; pair coverage 0.0%; required symbols 3,885; completely missing symbols 3,885; monthly minimum 0.0%; restored required pairs 40,048; restored pair coverage 0.0%; accepted=false.
- `CAP1000_PIT`: required 310,831; present 0; missing 310,831; pair coverage 0.0%; required symbols 1,886; completely missing symbols 1,886; monthly minimum 0.0%; restored required pairs 15,492; restored pair coverage 0.0%; accepted=false.
- all five frozen checks failed for both arms.
- strategy returns opened=false; model scores opened=false; production writes=false.

The missing-pair artifacts therefore identify the entire required candidate-date set as missing. This is a pure transport/data-acquisition failure, not strategy evidence.

## Current action: retry only the missing universe
Because `raw_unique_symbol_dates=0`, every required symbol/date pair is missing; the missing-symbol union is therefore the full required NOCAP symbol set. Commit `6fcf600245e0a04b3d8bc9c3f6c566a81c9fa03d` triggered retry run `34810592135` using the hardened transport policy and `max-parallel: 2`.

At the 2026-09-14 15:41 JST worker scan, GitHub's run-level endpoint still reported `queued`, but job-level inspection showed the workflow had materially advanced into acquisition: `fetch (0)` and `fetch (1)` were both `in_progress` at step `Fetch raw 1H shard`; the other ten shard jobs remained queued by the intentional `max-parallel: 2` cap. In both active jobs the daily materializer artifact was downloaded and verified, and the shard fetcher compile/contract step had already passed before entering raw acquisition. No duplicate retry was launched.

This is the missing-only retry in the only practical Yahoo form: each missing symbol is requested once and Yahoo returns its available 730d 1H chart; no non-missing symbol exists to exclude. The acceptance scope remains the emitted candidate-date pairs only. No threshold lowering, interpolation, candidate dropping, alias substitution, or return-aware provider choice is allowed.

## Frozen next action
1. Do not duplicate-trigger while raw retry `34810592135` is active.
2. After it finishes, rerun the exact frozen coverage verifier against retry artifacts; do not inspect strategy/model outcomes first.
3. If coverage still fails, retry only the newly emitted missing symbol/date set/codes. Keep all thresholds unchanged and do not interpolate.
4. Only if both `NOCAP` and `CAP1000_PIT` pass may clean feature materialization start. Recompute cross-sectional features separately per arm; PIT nominal `log_price`, split-normalized relative-price technicals, PIT daily-volume technicals, unchanged raw-1H-volume technicals.
5. H2 return targets remain sealed. DEV H1 remains strict5/no replacement/0.5% round-trip cost, mean first; near tie Top3-ex -> median -> NOCAP.
6. V45 ATR remains deferred until V47 completes.
