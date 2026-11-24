# Report Quality Checklist

Use this checklist before writing `premium_worker/out/premium_reports.json` and during dry-run repairs.

## Per-Symbol Evidence Packet

For each claimed alert, keep a compact internal audit row:

| column | requirement |
|---|---|
| alertId | exact claim alert ID |
| symbolCode | JPX code from claim |
| receivedAt | claim received time |
| newest disclosure checked | newest visible item on official/IRBANK/Yahoo sources |
| selected material disclosure | disclosure(s) used in the report |
| direct disclosure count | number of direct URLs in `開示リンク` |
| Sources count | 2-4 reference/listing pages |
| business/KPI | company-specific driver such as ARR, same-store sales, order backlog, utilization, dilution, cash flow, buyback, dividend, margin, or funding terms |
| unresolved risk | company-specific risk that belongs in `注意点` |
| impact label | one of the four allowed labels with a source-grounded sentence |

## Disclosure Selection

- Sort candidates by disclosure datetime descending.
- Always open and scan the newest routine-looking filing before ignoring it.
- Use the newest fundamentally material disclosure. If a newer material item exists, an older disclosure cannot be the main report anchor.
- Include same-date/same-time material bundles together, such as results plus dividend, buyback, capital policy, guidance, M&A, monthly data, financing, warrant exercise, or governance/regulatory notices.
- Routine governance, personnel, shareholder meeting, and organization notices can be left out only after confirming they do not affect control, capital policy, listing status, business operations, financing, or governance risk.

## Field Standards

`材料インパクト`:
- Format: `ラベル：材料/イベント + business effect or risk`.
- No `YYYY-MM-DD` dates.
- No title fragments, ellipses, English disclosure-title fragments, or research-process wording.
- Prefer 45-80 Japanese characters after the label; never pad with generic wording.

`事業概要`:
- Describe the actual business only.
- Do not discuss revenue growth, margins, capital policy, monthly sales, dilution, or financial KPIs here.

`足元材料`:
- Use `M月D日` for dates.
- Explain what changed and why it matters for this company.
- Do not list disclosure titles without connecting them to business impact.

`ファンダ要点`:
- Choose the KPI/accounting line that fits the company.
- Start directly from the KPI or mechanism.
- Include figures from the disclosure when available.

`注意点`:
- State the unresolved company-specific risk.
- Tie uncertainty to a KPI, financing condition, dilution pace, margin, order, utilization, customer concentration, or governance point.

## Link Standards

`開示リンク`:
- Use direct PDFs, TDnet `td_download.cgi`, `f.irbank.net/pdf/...`, `f.irbank.net/pr/...`, or official individual disclosure/detail pages.
- Do not use `https://irbank.net/<code>/<documentId>` HTML pages.
- Avoid long Yahoo edge-storage URLs when a shorter verified direct URL exists.
- Use labels in `YYYY-MM-DD 開示タイトル(hh:mm)` format.
- Keep the combined field under 1000 characters when possible.

`Sources`:
- Use company IR/news pages, IRBANK list pages, Yahoo Finance disclosure pages, JPX/TDnet list pages, or business/profile pages.
- Do not include direct PDF files or individual disclosure pages.
- Deduplicate by URL.

## Dry-Run Repair Pattern

When `post --dry-run` fails:

1. Read every failed `alertId` and symbol listed by the dry-run.
2. Reopen `latest_claim.json` and the current report.
3. Reopen official IR/news, IRBANK, and Yahoo/TDnet/JPX-equivalent list pages.
4. Patch all listed failed reports in one pass; leave every unlisted report unchanged unless the issue is structural.
5. Rerun dry-run.
6. Repeat until clear, then post.

Common validator messages:

- `may be stale`: include or explicitly account for the newer material disclosure.
- `source link must be a reference/listing page URL`: move direct disclosure/detail links from `Sources` to `開示リンク`.
- `disclosure link must be a direct disclosure URL`: replace listing/IRBANK HTML with verified direct PDF/detail URL.
- `too generic` or field-specific failures: rewrite with concrete KPI, figure, business effect, or risk.
- title/date mismatch: align `開示リンク` label with the validator-visible disclosure title and timestamp.
