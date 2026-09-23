# Historical fundamental snapshot — 2026-06-08|4422

Create exactly one evidence-grounded Japanese fundamental report for the existing report contract. Output only one JSON object with `identity` = `WEAK_EARLY_HISTORICAL_FUNDAMENTALS_BATCH_V1`, `reports` = a one-element array, and one report. Save the final JSON to `weak_early_beta/fundamental_worker/out/historical_backfill_candidate_reverse2026_jun08_4422_raw.json` using `--output-last-message` from the caller.

## Identity and hard cutoff
- signalDate: `2026-06-08`
- symbolCode: `4422`
- companyName: `ＶＡＬＵＥＮＥＸ`
- analysisCutoff: `2026-06-08T16:15:00+09:00`
- exact selectorNames: `2条件一致リバウンド`, `出来高沈静リバウンド`, `陰線沈み込みリバウンド`, `静かな売られ過ぎバランス`
- Use only information publicly available by 2026-06-08 16:15 JST. Do not use or mention the June 10 Q3 release, later share prices, or realized returns.

## Primary-source bodies reviewed
1) VALUENEX consolidated 2026/7 interim results, 2026-03-12 15:30 JST, official JPX PDF: https://www2.jpx.co.jp/disc/44220/140120260310578680.pdf
- Interim revenue ¥423.417m (+64.6% YoY); operating profit ¥61.939m (prior-year interim operating loss ¥126.412m); ordinary profit ¥64.757m (prior loss ¥126.121m); parent-attributable interim profit ¥64.492m (prior loss ¥125.457m).
- Consulting-services revenue ¥247.833m (+177.6%); ASP-services revenue ¥170.972m (+4.8%).
- Interim cash and equivalents ¥688.713m; total assets ¥897.499m; liabilities ¥123.291m; equity ratio 86.0%.
- Operating cash flow was negative ¥3.073m; investing cash flow negative ¥16.891m; no financing cash flow. The operating cash deficit was mainly due to a ¥76.887m reduction in advances received, despite interim profit.
- Management said a reasonable full-year forecast was difficult to calculate and provided no 2026/7 full-year forecast. This is an interim period only, not a full-year turnaround confirmation.
- Company provides algorithm-based analysis services for text and document data, including consulting and ASP/software services.
2) Company release `特許庁のプロボノ事業で当社ツールを提供`, 2026-04-17 12:00 JST, company-authored release mirrored at https://finance-frontend-pc-dist.west.edge.storage-yahoo.jp/disclosure/20260417/20260417505832.pdf
- The company supplied its tool for research/analysis during the Patent Office-sponsored startup and successor-entrepreneur pro bono matching program. The release does not disclose a contract amount, ongoing adoption, or earnings contribution. Do not portray it as a material order or revenue catalyst.
3) `上場維持基準への適合に関するお知らせ`, 2026-02-27 16:00 JST, official JPX PDF: https://www2.jpx.co.jp/disc/44220/140120260227571928.pdf
- The company said it complied with all Growth Market listing-maintenance criteria as of 2026-01-31, after free-float market capitalization was ¥4.94bn vs ¥5bn at 2025-07-31, rising to ¥5.93bn by 2026-01-31; the other listed criteria were also in compliance. This reduces the specific historical listing-maintenance concern at this cutoff; do not imply compliance guarantees future status.

## Source-index checks
- Official IR documents library, which lists the March 12 interim results: https://www.valuenex.com/ir-docs
- Disclosure chronology cross-check: https://finance.yahoo.co.jp/quote/4422.T/disclosure
- The company release PDF and both selected JPX disclosure bodies above have been reviewed. Selected disclosures must exactly match URLs and dates in the `開示リンク` field.

## Analysis framing
Balanced/as-of read: strong first-half revenue and return to interim profitability, driven mostly by consulting, with a comparatively stable ASP line; sound interim equity ratio and cash holdings. Temper the improvement: no full-year forecast, cash flow remained slightly negative from lower advances received, and one half does not establish sustainable full-year profitability. The Patent Office use case is visibility/reference value only with no disclosed economics. The listing criteria were compliant as of the stated date, subject to future performance and market conditions. Suggested materialImpact `混在/要確認`.

## JSON contract
Return report fields: `signalDate`, `symbolCode`, `companyName`, `analysisCutoff`, `summary`, `materialImpact`, `selectorNames`, `fields`, `sourceChecks`, `disclosures`, `auditStatus`, `auditNotes`.
Use these exact field names in this order in `fields`: `材料インパクト`, `事業概要`, `足元材料`, `ファンダ要点`, `注意点`, `開示リンク`, `Sources`. Reader-facing field bodies must be plain text, not HTML or Markdown, with no bold markup. The existing report renderer styles labels; body text stays normal weight.
`sourceChecks` must contain `official_ir` and `irbank_or_tdnet`, each with singular `url` and a concise Japanese `result`. `disclosures` should contain the three selected primary-source documents above, each with exact `title`, timezone-qualified `publishedAt`, exact `url`, and `contentReviewed: true`; no post-cutoff sources. The `開示リンク` field must include exactly these three URLs, with date/title/time, in reverse chronological order. `Sources` should link the official IR library and disclosure chronology page.
Set `auditStatus` to `pass` only if all identity, cutoff, exact selector names, facts, dates, source URLs and report/JSON contract above are satisfied. `auditNotes` must be `[]` when passed. Do not make a rating, price target, investment recommendation, or current-date claim. Output strict JSON only, without fences or commentary.
