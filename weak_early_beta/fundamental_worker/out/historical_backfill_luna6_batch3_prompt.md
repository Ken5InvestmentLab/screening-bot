# Historical fundamental backfill — batch 3 (two pending identities)

Use GPT-6 Luna (`gpt-6-luna`) with `xhigh` reasoning. This is a research-only run for exactly the two `pending` identities listed below. The already-published Feature (4052) analyses for 2026-09-02 and 2026-09-03 are not part of this batch: do not regenerate, overwrite, import, or repost them.

## Local-read route and allowlist

- Reproduce the successful September 2/3 local execution path: use `manual_run_config.json`'s pinned `nodePath`, `cliJs`, and `codexHome`; run Codex with `cwd` and `--cd` set to the configured weekly_report_gas root; pass this prompt as UTF-8 stdin and write only the final candidate through `-o`. Do not invoke the unrelated global `codex` found on `PATH`.
- In the successful run, local files were read by explicit absolute paths under the Unicode OneDrive checkout. The temporary `V:`/`W:` aliases are a verified fallback if the caller's path transport cannot resolve those exact paths; do not broaden the search.
- Read only these local files: `V:\weak_early_beta\fundamental_worker\out\historical_backfill_batch.json`, `V:\weak_early_beta\state\detections.csv`, `W:\premium_worker\AUTOMATION_PROMPT.md`, `W:\premium_worker\FUNDAMENTAL_EXAMPLES.md`, and `C:\Users\ken5\.codex\skills\premium-fundamental-snapshot\references\report_quality.md`.
- Do not search `C:\Users`, `C:\automations`, `C:\Documents`, `.claude`, or other unrelated directories. If an allowlisted file cannot be read, stop and report the exact path; do not broaden local search.
- Use web search to open the companies' official IR/news pages, IRBANK disclosure list, and TDnet/JPX or equivalent disclosure list. Open and read every direct primary source used; search snippets alone are not evidence.
- Return the JSON candidate in the final response. The caller writes it only through Codex CLI `-o` to `V:\weak_early_beta\fundamental_worker\out\historical_backfill_luna6_candidate_batch3.json`. Do not write another local file yourself.

## Scope and exact cutoffs

Include exactly these reports:

1. Identity `2023-01-06|3133`; company `海帆`; `signalDate` `2023-01-06`; `analysisCutoff` `2023-01-06T16:15:00+09:00`; selectors: `2条件一致リバウンド`, `出来高沈静リバウンド`, `地合い安定・2条件一致`, `陰線沈み込みリバウンド`, `静かな売られ過ぎバランス`.
2. Identity `2023-02-02|7037`; company `テノ．ホールディングス`; `signalDate` `2023-02-02`; `analysisCutoff` `2023-02-02T16:15:00+09:00`; selectors: `2条件一致リバウンド`, `出来高沈静リバウンド`, `地合い安定・2条件一致`, `陰線沈み込みリバウンド`, `静かな売られ過ぎバランス`.

Do not use information published after each exact 16:15 JST cutoff, even if it concerns an earlier period. Do not use later performance, later disclosures, or any post-cutoff hindsight. For 3133, a Jan 6 17:00 payment-completion notice is after cutoff and must be excluded; the Dec 27 allotment announcement may be described only as announced but not yet paid by cutoff if its original disclosure body supports that distinction.

## Report contract

Return one JSON object with `reports` containing exactly the two requested reports. Each report must include `signalDate`, `symbolCode`, `companyName`, `analysisCutoff`, `summary`, `materialImpact`, `selectorNames`, `fields`, `sourceChecks`, `disclosures`, and `sources`.

`fields` must be an array of seven `{ "name": ..., "value": ... }` objects in this exact order: `材料インパクト`, `事業概要`, `足元材料`, `ファンダ要点`, `注意点`, `開示リンク`, `Sources`.

- Use the Premium instructions/examples and report-quality checklist for company-specific, evidence-grounded Japanese analysis. Read the selected disclosure bodies before assigning an impact label.
- Use only one allowed impact label: `ポジティブ材料`, `ネガティブ材料`, `様子見`, or `混在/要確認`; follow it with a concise `：根拠要約`.
- No buy/sell recommendations, target prices, extra score, or statements about eventual outcomes.
- `sourceChecks` must include `official_ir` and `irbank_or_tdnet`, with URLs and concise results. `Sources` contains reference/listing pages, not PDFs or individual disclosures.
- Each selected `disclosures` item must have exact title, publication timestamp with `+09:00`, direct HTTPS document URL, and `contentReviewed: true`. Do not guess publication times. If exact time or body cannot be verified, exclude that claim/source and state the limitation.
- `開示リンク` contains only direct verified primary document/detail links used in the analysis. Keep the full field below 1000 characters where possible.
- Keep `summary` consistent with the material-impact field and the exact cutoff.
- Preserve the two identities and selector lists exactly; do not infer or add new detections.

No Discord, webhook, historical poster, live Premium Worker, claim/state, spreadsheet, HTML, manifest, detection ledger, source code, workflow, Git, or production changes. No real or dry-run post. Do not import; the caller will validate/import only after independent schema/as-of validation.

Return only the JSON object.
