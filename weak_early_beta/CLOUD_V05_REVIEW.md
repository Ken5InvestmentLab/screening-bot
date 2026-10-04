# Cloud v05 review

Review branch: `codex/cloud-analytics-d6-member-preferences`; draft PR #16 targets
`research/weak-early-beta`. No main change, production deployment, send, key or
database creation. Existing Discord notification behavior is preserved.

## User-visible change

The selected price cap, separate year, D5/D6 exit, share size and two-sided cost
recalculate comparison, payoff, annual/monthly performance, capital, charts and
CSV from the same validated public rows. Settings precede history; desktop rows
show five main fields and mobile cards use the same expandable details. Monthly
and history tables page by 20. Cash-flow lines step at recorded settlements and
never interpolate unobserved daily prices. Empty overlap bins show a dash.

History CSV names its allocation explicitly. When comparing both allocations,
history uses the equal-share method; the aggregate CSV contains both methods.
Reference rows retain their reviewed exclusion and full reason. Missing prices,
P/L and returns remain blank. Private provenance stays in source evidence,
outside public HTML metadata and the preview server's document root.

Public audience filtering precedes HTML generation. Free files contain only
identities with a verified observed D6 open; paid-only pending rows do not enter
free HTML, JSON, links or CSV. Cloud requires independently verified Whop paid
eligibility in addition to the existing session, with no role-cache grace.
Only new-detection and 08:00 JST reminder preferences remain. Legacy result
opt-ins are removed on read and legacy result candidates cannot become eligible.
There is no push sender in this revision.

## 4052 evidence and ongoing capture

Private `state/reviewed_forward_4052_20260930.csv` is a four-session Yahoo response
with actions, repair and unadjusted close requested. SHA-256:
`7baa3a8e025bd1b196de894cbc5c136c85921020fb791f207423e6efe5117b89`.
The pinned JSON manifest records the provider, request and observation time
`2026-10-04T03:50:00.952009+00:00` (manifest SHA:
`01093003d13e71c005bc6692c49fccb56c39d76015e9373c4f252da03870f647`).
September 29 actual close is 999 yen; September 30 is 1,149 yen. The reviewed
overlay supplies only the missing signal-close receipt in a copy. It neither
rewrites canonical economics nor unlocks missing D6. The dry-run adapter shares
that view and enforces its observation cutoff. Normal future daily capture uses
`model.attach_forward_rows` and `refresh_forward_endpoints`; frozen D5 does not
prevent new signal-close/D6 receipts.

## Detector scope and deployment limits

At checked Cloud base `0dc12cb5d8a6acd226a830d3e83ebc84e368986e`, CLI daily obtains
the JPX universe and daily prices. `model.prepare_live` then applies
`eligible_live_rows` to both labeled training rows and prediction candidates:
previous session actual close <= 1,000 yen, liquidity, current-price and usable
source requirements. Market-relative features also use full-universe context.
This is full-universe collection/context, not inference on every stock.
The independent display cap uses the detection-day actual close. Hence 4052 can
pass the prior-day detector filter and fail the selected 1,000-yen display cap.
No detector parameter or training path was changed here.

Runner source invokes `daily --refresh-live`; documentation identifies the local
17:00 JST task. The active runner configuration/cache was not available for
inspection. The live Worker redirects to Discord authentication, so authenticated
live layout and deployed SHA were not verified. A deployment tag alone is not
deployment proof. The read-only GitHub deployment-workflow collection request
was rejected by the connector URL allowlist; no alternate access was attempted.

Production setup remains separately required: D1 bindings/migrations, verified
Discord↔Whop identity links and live Whop account/product/paid-plan credentials,
private candidate import, then an approved browser subscription/VAPID/service
worker/sender implementation with fresh eligibility immediately before dispatch.
See `../weak-early-beta-gate/CLOUD_MEMBERSHIP_SETUP.md` for the tested contract.

## Local validation (2026-10-04)

- Python discovery `test_weak_early_beta*.py`: 220 passed, including the four
  requested core suites; 21 related tests also passed after the final CSS fix.
- Cloud gate `npm run check`: 200 passed, types/TypeScript and Wrangler dry-run
  passed; latest 16 HTML pages, three public scripts and assets synchronized.
- Independent Python oracle against the real browser: 48 scenarios, two
  allocations and eight metrics each, plus free isolation; 769 assertions passed.
- Actual Edge desktop 1440px and touch-enabled mobile 390px: 47 final flow
  assertions passed. Downloaded history/aggregate CSV totals agree; tested
  references, missing prices, price boundary, paging, keyboard details, empty
  overlap bin, mobile chart legibility and full/free output. Both themes were
  visually inspected. A mock paid member saved/reloaded settings with blocked
  localStorage; notifications remained opt-in and result opt-in was absent.
- Report regeneration preserved every existing source-state file byte-for-byte.
  Canonical detections SHA-256 remains
  `7574c18d72948e8faa3b1e0e8d718690242750f5459e68a3f98d7e18b9a55909`.

Evidence is in the executor workspace `qa/v05/` (test logs, assertion JSON,
actual CSV downloads and screenshots); it is not a production asset. Live Whop
credentials, authenticated production rendering and real push delivery were not
tested. No claimed result depends on an actual notification being sent.
