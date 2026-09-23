# Historical fundamental backfill — new records in batch 1

Use GPT-6 Luna with xhigh reasoning. This is a research-only run. The existing September 2 and September 3 Feature (4052) analyses are already present in the project history and have been posted; inspect their successful runner path if useful, but do not regenerate or repost those two analyses. Generate only the two new Kaihan snapshots below. Do not modify other files, Discord, production, or Git.

## Execution instructions

Follow the successful local route documented in `scripts/windows/weak-early-beta-fundamental-runner.mjs`: use the Premium Worker snapshot workflow, read its `AUTOMATION_PROMPT.md` and `FUNDAMENTAL_EXAMPLES.md`, plus the `premium-fundamental-snapshot` skill reference `references/report_quality.md`. Use the existing local repository data only for the two exact identities below. The final response is one importer-compatible JSON object with `reports` containing exactly two reports; the caller writes it to the candidate output file. Do not post, deploy, commit, or push.

## Rules

- Strictly as-of each cutoff. Use only information publicly disclosed on or before it. No post-cutoff news, subsequent results, later price action, or hindsight.
- This is company-specific descriptive analysis, not investment advice. No buy/sell recommendation, target price, numeric score, or inference about eventual outcomes.
- Each report must contain `signalDate`, `symbolCode`, `companyName`, `analysisCutoff`, `summary`, `materialImpact`, `selectorNames`, `fields`, `sourceChecks`, `disclosures`, and `sources`.
- `fields` must contain seven nonempty values in this exact order: `材料インパクト`, `事業概要`, `足元材料`, `ファンダ要点`, `注意点`, `開示リンク`, `Sources`.
- `sourceChecks` must include HTTPS links with roles `official_ir` and `irbank_or_tdnet`: `https://kaihan.co.jp/ir.html` and `https://irbank.net/td/3133`.
- Each disclosure actually used must have exact title, exact publication timestamp including JST timezone, direct HTTPS PDF/document URL, and `contentReviewed: true`; independently review the document body. Do not treat a search snippet or index page as a reviewed primary disclosure. If a source cannot be verified, exclude its claims and state the limitation.
- `開示リンク` includes direct document links. `Sources` names the issuer IR and disclosure list. If an exact publication time cannot be verified, do not guess. Do not add sources after Jan 5, 2023 16:15 JST.

## Required reports

1. `2023-01-04|3133`, company `海帆`, `signalDate` 2023-01-04, `analysisCutoff` `2023-01-04T16:15:00+09:00`, selectors: `2条件一致リバウンド`, `出来高沈静リバウンド`, `陰線沈み込みリバウンド`, `静かな売られ過ぎバランス`.
2. `2023-01-05|3133`, company `海帆`, `signalDate` 2023-01-05, `analysisCutoff` `2023-01-05T16:15:00+09:00`, selectors: `2条件一致リバウンド`, `出来高沈静リバウンド`, `地合い安定・2条件一致`, `陰線沈み込みリバウンド`, `静かな売られ過ぎバランス`.

## Source leads to verify from document bodies

- 2022-11-10 Q2 consolidated results: sales ¥905.3m, operating loss ¥282.0m, ordinary loss ¥323.5m, net loss ¥396.7m; FY forecast undecided; cash ¥746m, equity ratio 5.8%, operating cash flow -¥412m. PDF: `https://f.irbank.net/pdf/20221110/140120221110562184.pdf`.
- 2022-11-22 progress disclosure: subsidiary loan of ¥305m to Meta Energy at 1%, due 2023-03-31, collateralized by solar equipment/land in Hitachi (1,520.6 kW); borrower had no capital/personnel/related-party connection, although consulting contract had been signed; earnings effect described as minor. PDF: `https://f.irbank.net/pdf/20221122/140120221122569586.pdf`.
- 2022-12-01 payment completion for stock options. PDF lead: `https://f.irbank.net/pdf/20221201/140120221201573459.pdf`.
- 2022-12-05 store renovation / fixed-asset acquisition, approx. ¥55m, earnings effect described as light. Find and verify the direct PDF.
- 2022-12-07 correction to the 12/05 subsidiary asset acquisition: seller Sun Life Corporation capital corrected from ¥800m to ¥80m; schedule unchanged; earnings effect light. Reviewed PDF: `https://f.irbank.net/pdf/20221207/140120221207575839.pdf`.
- 2022-12-15 six solar-generation assets, roughly ¥13m each, expected 130–141 MWh per site annually, planned operation October 2023; earnings effect light. PDF: `https://www2.jpx.co.jp/disc/31330/140120221215579336.pdf`.
- A separate 2022-12-15 capital-reserve/capital-change schedule notice was indexed; use it only if you can verify its direct primary body and publication time.
- 2022-12-22 shareholder benefit kept the annual ¥2,000 meal voucher and extended eligible New Jidai stores, including franchise stores; earnings effect light. PDF: `https://f.irbank.net/pdf/20221222/140120221222582261.pdf`.
- 2022-12-27 subsidiary third-party allotment/name change: EST issued 30 common shares for ¥1.5m for HANARE sweets-shop business; Kaihan retained 66.67%, HANARE 33.33%; funds for product development/staff; consolidation from Q4; earnings effect light. PDF: `https://www2.jpx.co.jp/disc/31330/140120221227584081.pdf`.
- Jan 6, 2023 17:00 payment-completion disclosures occurred after both cutoffs and must be excluded; exclude Jan 12 and all later disclosures as well. For both reports, the Dec 27 financing was announced but not yet paid by the cutoff.

Return only the JSON object, with exactly the two requested reports.
