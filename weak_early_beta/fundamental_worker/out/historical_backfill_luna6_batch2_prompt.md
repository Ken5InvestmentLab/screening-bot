# Historical fundamental as-of audit — batch 2

Use GPT-6 Luna with xhigh. This is a bounded audit of two existing Feature (4052) reports, not a request to repost or broadly rewrite them. The screening-bot checkout is explicitly mounted at `V:\`; weekly_report_gas is explicitly mounted at `W:\`. Use only the exact local paths below plus the public disclosure pages named below. Do not search `C:\Users`, `C:\automations`, `C:\Documents`, `.claude`, or any other unrelated directory. If one listed file cannot be opened, stop and report that exact path instead of searching elsewhere. The final JSON output path is `V:\weak_early_beta\fundamental_worker\out\historical_backfill_luna6_candidate_batch2.json`; the caller passes it with Codex CLI `-o`, so return the JSON in your final answer and do not ask where to save it or perform a separate write.

## Source reports

- Read `V:\scripts\windows\weak-early-beta-fundamental-runner.mjs` for the successful invocation path.
- `2026-09-02|4052`: run `git -C V:\ show 32cc4a7f042f30515ea3fa63e575e81d1474debf:weak_early_beta/fundamental_worker/out/premium_reports.json` and select the matching report.
- `2026-09-03|4052`: read `V:\research\WEAK_EARLY_FUNDAMENTAL_20260903_4052.json` and `V:\weak_early_beta\fundamental_worker\out\premium_reports.json`.
- Read exact mode membership from `V:\weak_early_beta\state\detections.csv` for each identity.
- Read `W:\premium_worker\AUTOMATION_PROMPT.md`, `W:\premium_worker\FUNDAMENTAL_EXAMPLES.md`, and `C:\Users\ken5\.codex\skills\premium-fundamental-snapshot\references\report_quality.md`.

## Audit objective and non-negotiable rules

- The existing analysis content is considered already completed. Preserve its seven field values verbatim except remove the stale explicit `23:59:59` reference from the 2026-09-02 warning field and make only minimal corrections necessary to meet the requested as-of rule.
- Exact cutoff is `2026-09-02T16:15:00+09:00` or `2026-09-03T16:15:00+09:00`, respectively. Check every direct disclosure cited in the original report against official IR/news and an IRBANK/TDnet-equivalent list, and open each selected primary document body. Only published materials at/before that exact cutoff may be used.
- Check same-date EDINET large-holder reports only if their original filing time is before cutoff and the primary filing body is accessible and reviewed. Do not infer materiality or contents from index snippets. If inaccessible, do not cite or assert it.
- Do not use information learned after either cutoff. The only previously identified candidates are Feature reports S100YYIX (2026-08-25 10:47), S100YZSH (2026-09-02 09:38), and S100Z07L (2026-09-03 09:40); verify their filing body and exact public time independently before deciding whether they belong in the existing analysis.
- If every original statement is supported by pre-cutoff primary documents, return a validated receipt preserving its content. If any material statement relies on later data or an important source cannot be verified, do not disguise the issue: return `auditStatus: "needs_repair"` and explain the exact issue; do not import that identity.
- No Discord, worker, spreadsheet, Cloudflare, HTML, source-code, Git, workflow, production, or main changes. Write only the final JSON candidate in the path supplied by the caller.

## Required output

Return one JSON object with `reports` containing exactly the two identities, plus an `auditStatus` field on each report (`pass` or `needs_repair`) and short `auditNotes`. Each passing report must have `signalDate`, `symbolCode`, `companyName`, exact `analysisCutoff`, `summary`, `materialImpact`, `selectorNames`, `fields` as an array of `{ "name", "value" }` objects in this order: `材料インパクト`, `事業概要`, `足元材料`, `ファンダ要点`, `注意点`, `開示リンク`, `Sources`; `sourceChecks` with `official_ir` and `irbank_or_tdnet`; and `disclosures` with exact title, timestamp including `+09:00`, direct HTTPS URL, and `contentReviewed: true`. `Sources` must be reference/listing pages, not direct PDFs.

The report should retain the original report's content, selectors, and factual tone. Do not add recommendations, scores, target prices, or claims about later outcomes. Do not post the historical analyses again; they already have Discord posts.
