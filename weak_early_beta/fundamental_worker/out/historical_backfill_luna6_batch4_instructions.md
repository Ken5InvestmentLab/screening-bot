# Historical fundamental backfill — bounded batch 4

Use **GPT-6 Luna (`gpt-6-luna`) with `xhigh` reasoning**. This is a research-only, four-identity batch. The fixed identity list and cutoffs are in `V:\weak_early_beta\fundamental_worker\out\historical_backfill_luna6_batch4_prompt.md`; analyze exactly those four rows and no others.

## Read the established analysis contract first

Read all of `W:\premium_worker\AUTOMATION_PROMPT.md`, `W:\premium_worker\FUNDAMENTAL_EXAMPLES.md`, and `C:\Users\ken5\.codex\skills\premium-fundamental-snapshot\references\report_quality.md`. Follow the same company-specific seven-field format and quality bar as the existing Premium Worker. Read the earlier Kaihan batch prompt and its candidate output only as audited background, not as a substitute for checking the January 6 cutoff.

## Evidence and as-of rules

- For each identity independently, use its exact `analysis_cutoff` from the batch manifest (16:15 JST on its signal date). Use only issuer/official exchange disclosures published at or before that timestamp.
- Check both the issuer's official IR/news listing and an IRBANK or TDnet/JPX-equivalent disclosure listing. Open and read the body of every primary disclosure used. Search-result snippets, titles, later summaries, future returns, and later prices are not evidence.
- Include exact Japanese title, publication timestamp with `+09:00`, direct HTTPS disclosure/PDF URL, and `contentReviewed: true` for each cited primary document. If exact time or document body cannot be verified, do not use its claims; disclose the limitation. Do not guess.
- Search a bounded recent disclosure window (roughly the latest 45 days before each cutoff) plus the latest available results/forecast and material company-specific disclosures needed to describe the business and financial condition. Do not pad with immaterial notices.
- For 3133, the January 6 cutoff is 16:15 JST. Its January 6 17:00 payment-completion notice, if found, is after cutoff and MUST be excluded. The 2022-12-27 allotment was announced but its payment was not yet completed by cutoff. Reuse the prior January 4/5 audited source work only as leads; independently confirm all statements remain true at January 6 16:15 and check for intervening disclosures.
- Do not combine the two 4586 dates: the February 8 report may include only disclosures published by February 8 16:15, while February 7 must exclude anything first published later.
- Do not infer materiality from headlines. Keep analysis descriptive, neutral, and non-advisory: no buy/sell recommendation, target price, numeric score, or hindsight about eventual results.
- Historical analyses must never be posted to Discord, and do not modify a live worker, spreadsheet, workflow, source code, report, ledger, manifest, or Git state.

## Output contract

Return one UTF-8 JSON object with a `reports` array containing exactly the four requested identities. For each report include `signalDate`, `symbolCode`, `companyName`, exact `analysisCutoff`, concise `summary`, `materialImpact` as `ラベル：根拠要約` (allowed labels: `ポジティブ材料`, `ネガティブ材料`, `様子見`, `混在/要確認`), exact `selectorNames` copied from the manifest, and `fields` as an array of `{ "name": ..., "value": ... }` objects in this exact order: `材料インパクト`, `事業概要`, `足元材料`, `ファンダ要点`, `注意点`, `開示リンク`, `Sources`. All seven values must be non-empty Japanese strings. `sourceChecks` must include HTTPS URLs with roles `official_ir` and `irbank_or_tdnet`. `disclosures` must contain only body-reviewed primary documents whose publication timestamps are at or before that report's exact cutoff. Add `auditStatus: "pass"` and concise `auditNotes` only when every material statement meets these requirements; otherwise set `auditStatus: "needs_repair"` and explain the exact missing proof without inventing it.

`開示リンク` contains only the direct documents actually used. `Sources` contains issuer IR and disclosure-list pages, not direct PDFs. Keep direct sources and publication dates clear in `足元材料`. If verified no relevant disclosure exists, explain the bounded checks in `noMaterialDisclosureReason` and keep the seven fields complete.

Write only the final JSON object to `V:\weak_early_beta\fundamental_worker\out\historical_backfill_candidate_luna6_batch4_raw.json`. Do not edit any other file. Return the same JSON as the final response so it can be inspected before import.
