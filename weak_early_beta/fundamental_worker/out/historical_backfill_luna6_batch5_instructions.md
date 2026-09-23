# Luna 6 xhigh — Historical Fundamentals Batch 5

This is a research-only bounded batch. Analyze only the four identities and exact cutoffs in `historical_backfill_luna6_batch5.json`:

- `2023-02-15|4586` メドレックス — `2023-02-15T16:15:00+09:00`
- `2023-03-15|7138` ＴＯＲＩＣＯ — `2023-03-15T16:15:00+09:00`
- `2023-03-16|7776` セルシード — `2023-03-16T16:15:00+09:00`
- `2023-03-20|7042` アクセスグループ・ホールディングス — `2023-03-20T16:15:00+09:00`

Use **GPT-6 Luna (`gpt-6-luna`) with `xhigh` reasoning**. Do not substitute another model. Before analysis, read these exact local references:

- `weak_early_beta/fundamental_worker/out/historical_backfill_luna6_batch5.json`
- `weak_early_beta/state/detections.csv` (only to verify canonical company names/selectors)
- `weak_early_beta/historical_fundamentals.py` (receipt contract)
- `C:\Users\ken5\OneDrive\Desktop\Product\天底極致スコアリングBot\weekly_report_gas\premium_worker\AUTOMATION_PROMPT.md`
- `C:\Users\ken5\OneDrive\Desktop\Product\天底極致スコアリングBot\weekly_report_gas\premium_worker\FUNDAMENTAL_EXAMPLES.md`
- `C:\Users\ken5\.codex\skills\premium-fundamental-snapshot\references\report_quality.md`

Follow the current Premium Worker writing/selection rules, adapted to the historical cutoff. There is no fixed disclosure-link count: select only the latest fundamentally material, primary-source documents actually used in the analysis; omit routine or weak background items. Keep the combined `開示リンク` field under 1,000 characters and `Sources` to 2–4 reference/listing pages. Do not turn the link field into an archive dump. `Sources` must not be direct PDFs or individual disclosure pages.

For each symbol, inspect its official company IR/news/disclosure listing and an IRBANK/TDnet-style listing, then open and read the body of each selected primary disclosure. Use only official company IR or TDnet/JPX primary documents, published on or before that identity's exact cutoff. Listing/search pages help discover titles and times but do not prove document substance. Do not use EDINET filings, outside commentary as factual evidence, after-cutoff releases, 2026 data, later prices, realized returns, or hindsight. Historical rows are never sent to Discord.

Research-specific discovery starting points (verify and filter all items by the relevant cutoff):

- 4586: `https://www.medrx.co.jp/ir/index.html`, `https://irbank.net/4586/ir`; known cutoff-valid primary leads include the 2023-02-10 FY2022 results (`https://www2.jpx.co.jp/disc/45860/140120230210506166.pdf`), the 2023-01-17 MRX-5LBT additional-trial update (`https://www2.jpx.co.jp/disc/45860/140120230117590329.pdf`), the 2023-02-07 MRX-9FLT European patent decision (`https://www2.jpx.co.jp/disc/45860/140120230207502510.pdf`), and the 2023-02-03 completion of the 24th stock acquisition-right exercise (`https://www2.jpx.co.jp/disc/45860/140120230203500260.pdf`). Check all document bodies and retain only materially relevant items.
- 7138: `https://www.torico-corp.com/ir/library/disclosure/`, `https://irbank.net/7138/ir`; cutoff-valid 2023-02-13 Q3 financial results (`https://www2.jpx.co.jp/disc/71380/140120230213507970.pdf`) and results presentation (`https://www2.jpx.co.jp/disc/71380/140120230213508415.pdf`). The 2023-03-01 buyback-progress notice is listed at 15:30; only include it if its official/TDnet primary body is accessible and read, and the actual update is materially informative beyond the January progress already disclosed in the Q3 materials. Do not infer its details from its title or secondary snippets.
- 7776: `https://www.cellseed.com/news/2023/ir/`, `https://irbank.net/7776/ir`; cutoff-valid FY2022 results (`https://www2.jpx.co.jp/disc/77760/140120230214510206.pdf`) and, if materially relevant after reading it, the company-issued UpCell ADVANCE FDA master-file notice (`https://www.cellseed.com/news/news_file/file/20230126_ir_1.pdf`). A master-file registration is not FDA approval; state that distinction if used. Do not use the later 2023-03-13 external seminar/video or any later material.
- 7042: `https://www.access-t.co.jp/ir/`, `https://irbank.net/7042/ir`; read the cutoff-valid company primary March 14 forecast/dividend revision (`https://www2.jpx.co.jp/disc/70420/140120230313529444.pdf`; list time 17:00 JST). Do not include or use the later March 22 business reorganization announcement.

An identity may pass only when every material claim is grounded in a body-reviewed, cutoff-valid primary document and required fields are complete. If a required primary document cannot be read, mark only that identity `auditStatus: "needs_repair"`, explain the missing proof in `auditNotes`, and do not invent the missing content. Passing reports must be suitable for immediate import; the caller will import only passing reports and regenerate the HTML immediately for that completed portion.

Return exactly one JSON object with a `reports` array containing these four identities, in manifest order. Each report must have `signalDate`, `symbolCode`, `companyName`, exact `analysisCutoff`, concise `summary`, `materialImpact`, exact `selectorNames` copied from the batch JSON, seven `fields` in this order (`材料インパクト`, `事業概要`, `足元材料`, `ファンダ要点`, `注意点`, `開示リンク`, `Sources`), `sourceChecks`, `disclosures`, `auditStatus`, and `auditNotes`.

- `materialImpact` and the `材料インパクト` field must start with one of `ポジティブ材料`, `ネガティブ材料`, `様子見`, `混在/要確認`, followed by `：` and one company-specific, substantiated sentence (maximum 90 Japanese characters after the label).
- Write the narrative fields in natural, company-specific Japanese. Avoid advice, target prices, score/return claims, generic boilerplate, and research-process narration.
- `sourceChecks` must have objects with roles `official_ir` and `irbank_or_tdnet`, each containing a checked HTTPS `url` and a concise result.
- Each `disclosures` item must contain the exact title, publication timestamp with `+09:00`, direct HTTPS primary-document `url`, and `contentReviewed: true`. Use only items actually discussed in the report. The `開示リンク` URLs must match the set of disclosure URLs exactly. Every timestamp must be at or before the cutoff.
- Use 2–4 unique reference/listing URLs in `Sources`; no direct PDFs there. Keep the full `開示リンク` field at 1,000 characters or fewer.
- No Discord posting, no modifications to live systems, no retuning, and no use of technical outcome/forward-return data.

Output only the JSON object, without Markdown fences or surrounding prose. The invoking Codex CLI will write the final message to `weak_early_beta/fundamental_worker/out/historical_backfill_candidate_luna6_batch5_raw.json`. Do not edit any other file.
