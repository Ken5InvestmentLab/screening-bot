# Consensus V47 raw1H rate-limit incident — 2026-09-14

Research-only. No production/main/Discord/Spreadsheet/Stable★6/Sniper/Mega/TradingView/watchlist-builder/updater changes.

## Observation
Authoritative daily PIT materialization `34799835035` passed and authorized Yahoo raw 1H acquisition run `34800587082`.

The raw run completed GitHub-level SUCCESS across all 12 shards, but transport failed under Yahoo rate limiting. An inspected shard requested 324 symbols and produced 0 successful symbols / 324 `http_429` errors / 0 rows. No strategy returns or model scores were opened.

## Formal diagnosis
Initial raw coverage run `34810149461` is not acceptance evidence: the verifier crashed on an empty gzip shard with `pandas.errors.EmptyDataError` before evaluating the frozen gates.

Commit `efc4a0c463a6246b884fd73ad0320256b6ce2949` changed only verifier failure handling: empty shards now count as zero available pairs instead of crashing. Frozen thresholds were unchanged. Contract test run `34810228288` completed SUCCESS.

Formal rerun `34810234454` completed and emitted the authoritative coverage receipt:
- top-level `accepted=false`
- `raw_unique_symbol_dates=0`
- NOCAP: 853,061 required pairs, 0 present, 853,061 missing, 0.0% pair coverage; 3,885/3,885 required symbols completely missing; monthly minimum 0.0%; restored coverage 0/40,048 = 0.0%.
- CAP1000_PIT: 310,831 required pairs, 0 present, 310,831 missing, 0.0% pair coverage; 1,886/1,886 required symbols completely missing; monthly minimum 0.0%; restored coverage 0/15,492 = 0.0%.
- all frozen coverage checks failed in both arms.
- strategy returns opened=false; model scores opened=false; production writes=false.

Artifact digest for the receipt/missing-pair bundle: `sha256:83c35186addada392a3117f7f97eaca2d7b189670ceee306bb2284328c8a06c3`.

Conclusion: this is a complete transport/data-acquisition failure, not strategy evidence.

## Outcome-blind mitigation
The fetcher was hardened without touching eligibility, model, score, target, features, or acceptance thresholds:
- alternate Yahoo query1/query2 chart hosts;
- persistent HTTP session;
- bounded exponential backoff with `Retry-After` support for 429/502/503/504;
- 0.55-second post-success pacing;
- 8 attempts per symbol;
- transport-policy metadata included in shard summary;
- workflow `max-parallel: 2` and timeout 180 minutes.

## Missing-only retry now active
The formal receipt says zero candidate-date pairs were present, so every emitted required pair is missing and every NOCAP required symbol belongs to the missing-symbol union. Commit `6fcf600245e0a04b3d8bc9c3f6c566a81c9fa03d` triggered raw retry run `34810592135` using the hardened transport settings.

Yahoo's chart endpoint returns a symbol time range rather than arbitrary isolated dates, so the transport request is symbol-targeted: only symbols belonging to the emitted missing set are requested. Acceptance remains restricted to the frozen emitted candidate-date pairs. There are no already-covered symbols to avoid in this retry.

## Frozen next action
1. Do not duplicate-trigger while `34810592135` is active.
2. When it completes, run the same frozen coverage acceptance against that retry's artifacts before any feature/model evaluation.
3. If still below threshold, retry only the newly emitted missing symbols/date pairs. No interpolation, threshold relaxation, candidate removal, alias substitution, or return-aware source selection.
4. Only exact coverage PASS for both arms permits V47 clean feature materialization.
