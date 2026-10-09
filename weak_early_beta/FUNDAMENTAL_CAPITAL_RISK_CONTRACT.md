# Cloud forward fundamental capital risk review

New Cloud analysis keeps recent material disclosures as the report's current
anchor and separately checks capital policies that remain in effect. There is
no fixed age limit for the latter: a warrant issued years ago is relevant until
its remaining rights are accounted for by the analysis cutoff.

Start with the latest pre-cutoff financial results and annual/semiannual filing
hosted by the company. Check the capital-structure notes and official IR/TDnet
history, then trace each instrument to its issuance terms and subsequent
exercise, amendment, cancellation or expiry notices. A partial exercise or
cancellation does not close the entire issue. Separate underlying shares from
newly issued shares, treasury-share delivery, already exercised rights and
split/consolidation adjustments. Any dilution percentage needs a verified
new-share numerator and issued-share denominator with matching dates/bases;
unavailable quantities remain unknown.

The runner stamps new analysis claims and their owned state with
`capitalRiskReviewVersion: 1`. Before saving the report it validates the internal
`capitalRiskReview` using `scripts/windows/weak-early-beta-capital-risk.mjs`.
Retries for these same claims retain the requirement even when an existing
claim-matched output is reused. Pre-existing completed snapshots, import-only
retries without that stamp and historical candidates keep their original
contract; this change does not reanalyse or rewrite them. Shared Premium
prompts, worker state, EDINET policy and the public seven-field format remain
unchanged.

The review records its version, exact `analysisCutoff`, `historyCheckedThrough`,
`status`, reviewed primary `documents`, per-issue `instruments` and `riskNote`.
Document IDs connect issuance and current balance/closure findings. Each
document includes its publication time, body-review assertion, page/section
locator and finding. Date-only publication evidence is allowed only before the
cutoff's JST date. All dates stay at or before the cutoff; no lower date bound
is applied.

- `outstanding` requires a reviewed financial baseline, history checked through
  the cutoff, an issuance reference and a remaining-balance reference for each
  resolved issue. Unknown underlying-share counts require an explicit reason.
- `none_confirmed` requires the same baseline/history checks, no unresolved or
  outstanding instruments, and `absenceEvidence` identifying a primary
  statement covering **all** dilutive instruments. No recent financing news,
  absence of diluted EPS or the closure of only one series is insufficient.
  Every issuance document already recognized in the review must be linked to
  its instrument; it cannot be dropped from the inventory to claim absence.
- `unresolved` records the missing evidence. Its exact company-specific
  `riskNote` must appear in `注意点`, as must a confirmed remaining risk's note.
  It can be saved with the uncertainty visible; it cannot be represented as
  confirmed absence. Missing origins/status documents must not be fabricated.

Important sources supporting user-facing claims also belong in `disclosures`
and `開示リンク` under the existing publication/link contract. The internal
document list can retain supporting history without expanding the public link
field beyond its existing limit.

This validator checks the evidence structure, reference/date consistency,
closure/balance contradictions and required risk disclosure. It cannot prove
that the latest financial document was discovered, that every issue was found,
that the quoted document actually says the declared finding, or that a website
is the issuer's official site. The analysis model must open and review the
primary bodies; human source review remains necessary when accuracy is in
doubt. An accepted structure is not proof of complete financial due diligence.
