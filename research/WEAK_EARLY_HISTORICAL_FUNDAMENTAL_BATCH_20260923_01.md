# Historical Fundamental Batch Receipt — 2026-09-23 / 01

- Identity: `WEAK_EARLY_HISTORICAL_FUNDAMENTALS_BATCH_20260923_LUNA6_01`.
- Branch: `research/weak-early-beta`; base SHA: `3ff1b89a403c4523b35de3f800e742373faf7798`.
- Model: GPT-6 Luna (`gpt-6-luna`), `xhigh`; research-only, no posting/deploying.
- Scope: `2023-01-04|3133` and `2023-01-05|3133` (海帆). Both as-of cutoffs are detection day 16:15 JST.
- Successful local-read route: create temporary `V:` and `W:` aliases for the screening-bot and weekly_report_gas roots, run the Codex CLI from `W:\`, with `--search -a never exec --ignore-user-config --skip-git-repo-check --sandbox danger-full-access --model gpt-6-luna -c model_reasoning_effort="xhigh" -c forced_login_method="chatgpt" --json`, and save final JSON under `V:\weak_early_beta\fundamental_worker\out\`. The aliases were temporary and removed after completion.
- Read the existing Premium Worker `AUTOMATION_PROMPT.md`, `FUNDAMENTAL_EXAMPLES.md`, and `premium-fundamental-snapshot/references/report_quality.md`; used official Kaihan IR plus IRBANK disclosure-list checks.
- Each report contains seven fields and eight body-reviewed direct disclosures. All published timestamps precede the corresponding 16:15 cutoff; no Jan 6 or later information was used.
- Raw model output: `weak_early_beta/fundamental_worker/out/historical_backfill_luna6_candidate.json`, SHA256 `D34D2C15E18E394BEA06E6BFC15F2714D6A990154F1EDDE55B6F87C1EC6DA3AC`.
- Import-normalized input: `weak_early_beta/fundamental_worker/out/historical_backfill_reports.json`, SHA256 `FA7E5FFAA73AB450792BE2D4E0E679E06E8B1B1E7D5751D54BCD478B6F8F2795`.
- Historical receipt store: `weak_early_beta/fundamental_worker/out/historical_backfill_receipts.json`, SHA256 `7BA0791FB9445840637F733EC0C534219EE46071A96822C9F3D69C6804BBEE9E`.
- Updated detection ledger: `weak_early_beta/state/detections.csv`, SHA256 `9FE31F2BAABB55CC08F47D03422C3D21CC541A47D8AAC77C7555831C4580253C`.
- Updated user report: `reports/weak_early_beta_latest.html`, SHA256 `3821F07008ECB1F36BA3ABE9416D156DDD6FE7910D1BC217A5A3249E46144E25`.
- Importer result: 2 imported; manifest now has 2 complete, 249 pending, and 2 prior Feature records still `legacy_needs_asof_audit`.
- Verification: both reports passed `validate_historical_report`; 8 disclosure timestamps per report are at/before cutoff; field order/count 7; `py -3 -m unittest tests.test_weak_early_beta` passed 24 tests.
- Historical Discord posts: 0. Production, main, live Premium Worker state, and Sheets: unchanged. 2026 remains SEALED for selection and retuning.
- Next: audit the two already-written 4052 reports against 16:15 cutoffs without reposting them; then process the next manifest batch. Stop new work when weekly remaining reaches 30%.
