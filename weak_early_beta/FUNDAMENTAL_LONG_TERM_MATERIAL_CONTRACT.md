# Cloud forward long-term material review

New Cloud snapshots examine old positive and negative business developments as
well as outstanding capital instruments. Recent news stays the current report
anchor; an old announcement enters the analysis when its consequences still
matter at the cutoff. There is no fixed lookback age limit.

Begin with the latest official financial results and current business progress,
then trace relevant alliances, orders/contracts, capacity investments, products,
approvals/subsidies, restructuring/M&A, legal/regulatory events and contract
changes to their original announcements and subsequent progress, start,
revenue/profit contribution, delay, cancellation or end. Cover both directions;
the scope is not limited to dilution or risks. Preserve the separate capital
review contract in `FUNDAMENTAL_CAPITAL_RISK_CONTRACT.md`.

Explain what a continuing matter means **now**, rather than listing old titles.
A company-disclosed start or monetization timetable and verified operational
milestones can support a conditional assessment: "if the announced plan holds,
this is near/in the expected monetization period, but actual contribution is
not yet verified." Passing time, an order value, award, approval, alliance or
completed facility alone does not prove revenue/profit recognition. Do not
create an undisclosed earnings forecast. Month/year-only schedules remain
company statements; do not invent exact dates.

`longTermMaterialReviewVersion: 1` is stamped into each new analysis claim and
owned state. The runner validates `longTermMaterialReview` before saving,
including on claim-matched output reuse. Legacy completed/import-only snapshots
and historical candidates keep their original contracts.

The internal review contains its version, exact cutoff, conclusion, checked
history cutoff, reviewed categories, a company-specific review scope, primary
documents and items. Documents have publication time, reviewed-body assertion,
page/section locator and findings. An item links its original announcement and
latest progress, declares positive/negative/mixed direction and one of
`planned`, `in_progress`, `contributing`, `delayed`, `ended`, `unresolved`.
Continuing or uncertain items must place their `currentAssessment` in the
existing public `足元材料`, `ファンダ要点` or `注意点`.

Optional `reportedTiming` holds the company's statement and document reference,
with an exact `dueDate` only if disclosed. A reached-date flag requires a
disclosed date before the cutoff's JST day and a specific risk note in
`注意点`. Month/year schedules can still support a conditional natural-language
assessment without that flag. `contributing` requires separate
`actualContribution` evidence for reported actual revenue or profit, never an
original promise or company forecast. Unresolved items retain their missing
evidence reason and exact risk note in `注意点`.

`active_materials` and `no_relevant_found` require review of all eight categories,
a current official financial baseline and history checked through the cutoff.
Every original announcement recorded as relevant evidence must be accounted for
by an item. `no_relevant_found` allows empty items or verified ended matters;
it means no continuing matter relevant to this analysis was found in the
reviewed sources. It is not a definitive assertion that no material exists.
Incomplete research uses `unresolved`, with the missing evidence visible.

Both validators use the same primary-document cutoff checks. Publication dates
are not bounded below. Direct EDINET evidence remains outside the existing
Cloud contract; use company IR or TDnet/JPX primary bodies. Important documents
supporting public claims remain in `disclosures`/`開示リンク` under their existing
link/date contract; supporting chronology can remain internal.

These checks enforce evidence shape, reference/date consistency, broad declared
coverage, public uncertainty and the separation of plans from claimed actual
contribution. They cannot prove source discovery is complete, that a source is
official, that every old event was found or that declared findings accurately
represent the document body. The model must perform primary-source research;
accepted structure is not proof of complete fundamental due diligence.

Verify with:

```
node --test scripts/windows/test-weak-early-beta-capital-risk.mjs scripts/windows/test-weak-early-beta-long-term-materials.mjs scripts/windows/test-weak-early-beta-analysis-cutoff.mjs scripts/windows/test-weak-early-beta-point-in-time-post.mjs
```
