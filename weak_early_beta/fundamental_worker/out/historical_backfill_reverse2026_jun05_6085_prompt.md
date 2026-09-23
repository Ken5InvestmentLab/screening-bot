# Historical fundamental snapshot — 2026-06-05|6085

Create exactly one evidence-grounded Japanese fundamental report for the existing report contract. Output only one JSON object with `identity` = `WEAK_EARLY_HISTORICAL_FUNDAMENTALS_BATCH_V1`, `reports` = a one-element array, and one report. Save the final JSON to `weak_early_beta/fundamental_worker/out/historical_backfill_candidate_reverse2026_jun05_6085_raw.json` using `--output-last-message` from the caller.

## Identity and hard cutoff
- signalDate: `2026-06-05`
- symbolCode: `6085`
- companyName: `アーキテクツ・スタジオ・ジャパン`
- analysisCutoff: `2026-06-05T16:15:00+09:00`
- exact selectorNames: `2条件一致リバウンド`, `出来高沈静リバウンド`, `地合い安定・2条件一致`, `陰線沈み込みリバウンド`, `静かな売られ過ぎバランス`
- Use only information publicly available by 2026-06-05 16:15 JST. No later reports, later prices, or realized returns.

## Primary-source bodies reviewed
1) Company `事業計画及び成長可能性に関する事項`, published 2026-06-05 14:45 JST, official JPX: https://www2.jpx.co.jp/disc/60850/140120260605564328.pdf
- FY2026/2 actual sales ¥659m, operating loss ¥559m, net loss ¥601m, compared with the older plan of sales ¥2,533m, operating profit ¥191m, net profit ¥130m. Management's hindsight explains that prior acquired-subcompany plans in lifestyle/investment did not produce the expected results and were cut away.
- Management's revised multi-year plan shows FY2027/2 sales ¥1,334m and operating profit ¥48m, then FY2030/2 sales ¥4,731m and operating profit ¥1,050m. These are company plan numbers in a growth-potential presentation, not an independently validated forecast; do not label them as realized results or an established forecast.
- The same presentation cautions that for PD/ALIN, revenue is mainly referral fees and they model sales as gross profit; the overseas/IT revenue structure is still undecided and sales are likewise treated as gross profit. These assumptions increase uncertainty around forecast margins and conversion.
- Core activities include its network of nearly 3,000 architects and architect-proposal/network/producer services. The company is repositioning toward architect proposal, environmental products and overseas/IT, including its Permits AI subsidiary.
2) `連結子会社の異動および特別損失の発生に関するお知らせ`, 2026-06-01 12:45 JST, official JPX: https://www2.jpx.co.jp/disc/60850/140120260601557293.pdf
- On June 1, the company transferred all 5,000 shares of wholly owned ESJ to a business partner for ¥1. ESJ had struggled to secure large projects and reported a 2026/3 standalone net loss expected at ¥13.535m.
- The disposal is part of the company's business restructuring. For FY2027/2, the company expects a consolidated affiliate-share disposal loss of ¥54m (parent-only ¥42m); impact to parent-attributable net profit is under review.
3) `上場維持基準（時価総額）への適合及び上場維持基準の適合に向けた計画（流通株式比率、純資産基準）に関するお知らせ`, 2026-05-29 14:20 JST, company-authored TDnet document: https://www.daiwair.co.jp/td_download.cgi?c=6085&i=3228027
- As of 2026-02-28 the market-cap criterion was met, with total market capitalization ¥6.9bn. However, free-float ratio was 16.2% vs the required 25%, and net assets were negative ¥220m vs a positive requirement. Improvement period ends 2027-02-28; if both are not cured, the notice describes managed-stock status followed by delisting on 2027-09-01.
- The company said its expected ordinary profit of ¥38m alone would not restore net assets by the end of February 2027; it planned operating-profit improvement and possible strategic/capital partnerships. Treat that as management statement, not a verified outcome.

## Source-index and timing checks
- Company official timely-disclosure page: https://corporate.asj-net.com/ir/library/timely-disclosure/
- TDnet date/time chronology: https://contents.webapi.yanoshin.jp/contents/tdnet/6085
- The three listed primary-source bodies were reviewed directly. The TDnet list confirms the exact publication times above. The chronology also includes later June/July/August information; exclude all of it.

## Analysis framing
Use a materially cautious, negative/mixed as-of read: FY2026/2 missed the former plan by a very wide margin and generated large losses; restructuring and return to the core could create a base for recovery, but the new growth plan is aggressive and relies on uncertain segments and gross-profit conventions. ESJ's ¥1 sale removes a weak subsidiary but adds the disclosed ¥54m FY2027 loss. The listing-continuity risk is acute until both the free-float and positive-net-assets standards are met by 2027-02-28. Do not imply automatic delisting now; state the conditional deadline.

## JSON contract
Return report fields: `signalDate`, `symbolCode`, `companyName`, `analysisCutoff`, `summary`, `materialImpact`, `selectorNames`, `fields`, `sourceChecks`, `disclosures`, `auditStatus`, `auditNotes`.
Use these exact field names in this order in `fields`: `材料インパクト`, `事業概要`, `足元材料`, `ファンダ要点`, `注意点`, `開示リンク`, `Sources`. Reader-facing field bodies must be plain text, not HTML or Markdown, with no bold markup. The existing report renderer styles labels; body text stays normal weight.
`sourceChecks` must contain `official_ir` and `irbank_or_tdnet`, each with singular `url` and a concise Japanese `result`. `disclosures` should contain the three selected primary-source documents above, each with exact `title`, timezone-qualified `publishedAt`, exact `url`, and `contentReviewed: true`; no post-cutoff sources. The `開示リンク` field must include exactly these three URLs, with date/title/time, in reverse chronological order. `Sources` should contain exactly 2-4 distinct reference/listing-page URLs, not additional PDFs; use the two reference pages above and optionally the company home page.
Set `auditStatus` to `pass` only if all identity, cutoff, exact selector names, facts, dates, source URLs and report/JSON contract above are satisfied. `auditNotes` must be `[]` when passed. Do not make a rating, price target, investment recommendation, or current-date claim. Output strict JSON only, without fences or commentary.
