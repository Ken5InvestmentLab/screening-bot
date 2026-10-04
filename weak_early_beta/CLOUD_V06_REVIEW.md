# Cloud v06 review

Review branch: `codex/cloud-analytics-d6-member-preferences`; draft PR #16 targets
`research/weak-early-beta`. This review supersedes the v05 UI and CSV descriptions.
No merge, production deployment, notification send, database/key creation or main
change was performed. Existing Discord behavior and detector settings remain.

## Visible behavior

The original Cloud logo, gradient hero and individual mode context are retained.
Desktop keeps all eight page links visible; mobile keeps history and analytics
visible and places the other six links under Other. Settings opens a native
dialog with Trial, Notifications and Display tabs. Draft values survive tab
switches. Each reset affects only its own tab; Save applies the draft, whereas
Cancel, X, backdrop and Escape discard it. The SVG close control is centered in
a 44px button. Save/reset and cancel have distinct primary/secondary styling.

Fresh defaults are detection-day actual close <=1,000 yen, D6 open, comparison
of both allocations, 100 shares, zero costs and dark appearance. Existing saved
server/device choices take precedence. Light/dark/system, small/standard/large
font and 20/50/100 rows are shared across pages on the device. Paid members' price,
endpoint, share, cost and notification preferences use the server member ID;
the preview accurately reports that its server API is unavailable.

Analytics has no visible detection list. Its minimal audience-filtered template
supplies the calculations; private provenance and raw canonical rows are absent.
History keeps important fields visible on desktop and wraps on mobile without
horizontal scrolling. Both allocations show separate actual shares, principal
and P/L lines. Positive P/L has a plus sign and green color, negative P/L is red,
and zero is neutral. Confirmed endpoint cells show their date and price without
redundant status; unknown prices remain blank with waiting/not-obtained status.

Each allocation has its own smooth asset curve and independently scaled currency
axis in ten-thousand yen. Curves preserve all observed settlement points and use
bounded cubic controls; they are not daily mark-to-market observations. Graphs
precede the related numbers. The retained explanation states that required
principal is added to realized P/L and that intermediate market prices are not
represented. Share explanations update to the selected base size and 3x example.

Profit Structure uses the original rounded diverging track. Annual horizontal
bars show the latest three years; an older-years control reveals complete rows.
The axis includes zero and only the visible years, shared by both allocations.
Positive bars remain blue/violet and negative bars red, with neutral value labels.
The annual/profit cards balance their height. Analytics full-period, annual and
monthly detailed tables share one metric ordering and formatting; those tables
permit horizontal scrolling with a sticky period column and mobile method label.

Every mode's graphs, payoff, capital and performance tables follow the selected
allocation. Proportional shares use the total matched modes for that date/symbol
before filtering to the current mode. Equal results are not artificially changed.
User-facing CSV buttons are removed. Internal history CSV for both allocations
contains two explicitly labeled records per signal, with corresponding costs/P/L.

## Data and audience boundaries

2022 is excluded from display and aggregation, with source data retained. Past
reconstruction and operational observations remain distinguished, including that
2026 reconstruction covers known past outcomes. Reference-only records remain
outside performance, and costs are applied consistently. Detection-day validated
actual close controls the presentation cap; raising it does not restore stocks
that the unchanged prior-day <=1,000-yen detector never detected.

D5 economics remain frozen while independently captured D6 dates, actual opens,
receipt status/time and provenance can be added. Audited overlays and explicit
backfill paths retain canonical protection. Corporate actions are incorporated
through D6 when computing D6 P/L; missing values are not zero or substitute prices.
Older pending rows lacking the scheduled D6 date derive it in the temporary view
only, aligning native and browser coverage without creating a price receipt.

Free output is generated from records with an actually acquired, verified D6 open.
Elapsed time or D5 completion alone does not release a symbol. Unreleased identity
and links do not enter free HTML, JSON, CSV or cache. Full/free sources are filtered
separately before generation. The simplified free notice explains this boundary
without internal receipt or population terminology.

Only new-detection and 08:00 JST confirmation-day reminder preferences remain;
result opt-ins were removed in the accepted v05 scope. Defaults are OFF. Morning
copy says today is the confirmation day and the price is not known. Readiness
reports member eligibility, browser permission and preparation without requesting
permission, registering subscriptions or sending. Strict fresh Whop paid status
is required for dry-run eligibility; unknown, expired and provider failures hold
delivery. Existing Discord role-cache grace cannot authorize dispatch. Dedupe and
delivery-ledger contracts are tested; this revision has no push sender.

## Default comparison and calculation

The comparison uses the same audited source, cutoff 2026-10-04, excludes 2022 and
reference records, and holds shares=100 and cost=0 across five caps and D5/D6.
Caps necessarily select different cohorts; each cohort uses its native observed
period denominator. Required capital is the peak simultaneous buy principal,
with purchases preceding same-day receipts. Capital growth is total realized
P/L / required capital. Simple annualization divides that by the covered years
(days / 365.2425); it is not compounded annual return. Pending prices are excluded
from P/L but their scheduled date contributes to coverage up to the common cutoff.

Within these proportional-allocation choices, 1,000 yen / D6 has the highest
capital growth (148.31%) and simple annualization (40.25%): 811 completed weighted
trades / 213 distinct signals, P/L 2,281,350 yen, required capital 1,538,200 yen,
win rate 48.83%, no pending trades. The highest win rate is 3,000 yen / D5 at
50.97%: 930 completed weighted trades, five pending, P/L 3,466,550 yen, required
capital 4,584,500 yen, growth 75.61%, annualization 20.17%. The accepted default
prioritizes capital efficiency; it does not maximize every metric or forecast
future results. Exact unrounded values are preserved in the independent evidence.

## Validation and limits

- Python Cloud discovery: 222 passed, including the four requested core suites.
- Gate `npm run check`: 207 passed; generated types, TypeScript and Wrangler
  deployment dry-run passed, including source synchronization.
- Independent native-versus-Edge oracle: 120 cases across audience, five caps,
  D5/D6, year selection and costs; 2,401 metric/privacy assertions passed.
- Actual Edge: 191 layout/interaction assertions across eight pages, 1440/390px,
  light/dark and three font sizes, plus 320px, system theme and blocked storage.
- Paid mock API: ten save/reset/cancel/failure/opt-in assertions passed. Focused
  final mode, wording and detailed-table checks supplement the broad run.
- Smooth-curve bounds and display-storage unit cases passed. Source-state hashes
  remained unchanged; detections SHA-256 is
  `7574c18d72948e8faa3b1e0e8d718690242750f5459e68a3f98d7e18b9a55909`.

Logs, oracle JSON and screenshots are executor evidence, not public assets.
Original/reference and current desktop/mobile views were rendered and visually
reviewed. Remote CI, live authenticated rendering/deployed SHA, live Whop/D1 and
actual push delivery remain unverified. The prior workflow read was rejected by
the connector URL allowlist; it was not bypassed.

Production still needs separately approved D1 bindings/migrations, a verified
Discord-to-Whop ID link and pinned Whop product/plan/webhook credentials, private
candidate import, and browser opt-in/service worker/VAPID/sender setup. No email
collection/send is introduced. See `../weak-early-beta-gate/CLOUD_MEMBERSHIP_SETUP.md`.
