# Entry revision isolation

## Scope
- Runs only in the daily CLI after existing source quality/revision validation.
- Recognizes a changed actual entry price on an already-entered, unfrozen forward trade using the unchanged strict tolerance.
- Does not change source prices, fixed entry costs, trade economics, or canonical historical data.
- Session/calendar inconsistencies and unknown failures still fail closed.

## Isolation
- Preflight collects all conflicting selector IDs before any endpoint mutation.
- Every row of that symbol is marked unusable through validated run-local evidence. Dates and original source data are retained.
- This uses the existing feature masking path: no indicators or market-breadth vote from that symbol. Other symbols continue. Cross-sectional population therefore excludes the held symbol, intentionally and explicitly, as with existing JPX symbol holds.
- All prior ledger rows/receipts/updated_at of the affected symbol remain unchanged.
- Authoritative cached CSV is not rewritten with the run-local hold. Every next run rechecks frozen entry costs against its validated input; no guessed resolution or forced price correction is performed.

## Evidence and notification
- Source SHA, original ledger SHA, symbol-row SHA, detection IDs, entry date, old/new prices are recorded in a sidecar adjacent to source-quality JSON before scoring.
- Daily receipt contains holds, sidecar path and SHA.
- Automated and standalone notify/notify-day require a same-day successful detection receipt, matching source CSV SHA, source-quality audit SHA/identity, hold audit SHA/content, and unchanged ledger entry cost before sending.
- Held symbols are omitted from pending signal delivery and daily completion counts; completion includes the held-symbol list when there are other successful new symbols.
- No-new-symbol days preserve the existing no-summary behavior; holds remain in the local daily receipt for the recovery summary.

## Not implemented
- No generalized catch-and-continue for arbitrary errors.
- No automatic official-source price repair, JPX parser fix, or reconciliation of a previously ambiguous remote send.
- No live deployment or network test performed by this change's author.
