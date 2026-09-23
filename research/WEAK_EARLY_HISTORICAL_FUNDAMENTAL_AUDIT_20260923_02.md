# Historical Fundamental As-of Audit — 2026-09-23 / 02

- Identity: `WEAK_EARLY_HISTORICAL_FUNDAMENTALS_AUDIT_20260923_4052_02`.
- Branch and starting HEAD: `research/weak-early-beta`, `41ec852e1fc47d741f4dac134d85f7d4987442ed`.
- Purpose: reproduce the successful local-read route used for the already-posted 2026-09-02 and 2026-09-03 Feature (4052) analyses; verify whether the existing text can be accepted as an exact 16:15 JST as-of snapshot. This was an audit only, not a Discord repost.
- Local-read route: temporary `V:` and `W:` drive aliases exposed the screening-bot checkout and weekly_report_gas checkout as short paths. The exact allowlisted files were read successfully through those aliases, including the runner, original reports, detection ledger, Premium instructions/examples, and quality reference. The historical prompt prohibited broad searches outside those paths. The aliases were removed after execution.
- Model/CLI: GPT-6 Luna (`gpt-6-luna`), `xhigh`, Codex CLI `exec` with `--search -a never --ignore-user-config --skip-git-repo-check --sandbox danger-full-access`; final candidate was written only to the caller-selected JSON output path. No live Premium claim/poster was run.
- PDF review: EDINET originals were fetched from the public EDINET document endpoint and reviewed with the already-installed PyMuPDF (`fitz`). `pypdf` extraction produced garbled Japanese for these PDFs, so it was not used as the review basis.
- Confirmed cutoff-visible filings:
  - `S100YYIX`, 2026-08-25 10:47:41 JST, [EDINET PDF](https://disclosure2dl.edinet-fsa.go.jp/searchdocument/pdf/S100YYIX.pdf): founder holding ratio 10.34% → 9.32%.
  - `S100YZSH`, 2026-09-02 09:38:25 JST, [EDINET PDF](https://disclosure2.edinet-fsa.go.jp/searchdocument/pdf/S100YZSH.pdf): 9.32% → 7.96%; 79,200 shares disposed in the market during Aug 18–31.
  - `S100Z07L`, 2026-09-03 09:40:37 JST, [EDINET PDF](https://disclosure2.edinet-fsa.go.jp/searchdocument/pdf/S100Z07L.pdf): 7.96% → 6.09%; 110,000 shares disposed in the market during Sep 1–2.
- Audit result: both existing reports remain factually supported on the financial disclosures they cite, but both are incomplete as of their requested cutoff because the same-day EDINET ownership-change filing was public before 16:15 JST and omitted from the analysis. Candidate statuses are `needs_repair`; do not import until the existing text is minimally amended with the reviewed filings and revalidated.
- No report, HTML, ledger, manifest, worker state, production component, Discord post, or spreadsheet was changed by this audit. The existing Discord posts were not duplicated or edited.
- Candidate prompt: `weak_early_beta/fundamental_worker/out/historical_backfill_luna6_batch2_prompt.md`, SHA256 `3E9F7F1DAE5EE49CB08B77032AAA27DEC64E12B7FBE9D9A611FEB62AFA28764A`.
- Audit candidate: `weak_early_beta/fundamental_worker/out/historical_backfill_luna6_candidate_batch2.json`, SHA256 `801AD099FA0DA68F68BF49C3CB696F16A006ED04C9EE327DB1BF2099A988C142`.
- Next: either minimally correct both 4052 reports for HTML/history while leaving their already-posted Discord messages untouched, or obtain user direction before changing those two user-facing historical snapshots. Continue the pending historical backfill with the same `V:`/`W:` local-read route and `gpt-6-luna` xhigh; do not use the live runner or post historical analyses to Discord.
