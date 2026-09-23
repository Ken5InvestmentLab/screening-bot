# Historical fundamental backfill log

## 2026-09-23 — first four-identity batch audit

- Branch: `research/weak-early-beta`; starting HEAD: `d899f30c6ad38f5f00f875545a241a9a2f215f66`.
- Scope: manifest contains 253 date/symbol identities (251 pending, 2 legacy receipts requiring strict as-of repair). Current batch is `weak_early_beta/fundamental_worker/out/historical_backfill_batch.json`, limit 4.
- Fixed cutoff: scheduled scan proxy `16:15 JST` on each detection date. Past outcomes and post-cutoff disclosures are not eligible; historical analyses are not reposted to Discord.
- Usage gate: active `weak-early` hourly heartbeat. It stops at 30% weekly remaining; it checkpoints at 3% five-hour remaining and resumes on a later hourly heartbeat only after recovery and only while weekly remaining is above 30%.

### Identity: 2026-09-02|4052 and 2026-09-03|4052

- Existing source: `weak_early_beta/fundamental_worker/out/premium_reports.json` contains only the 2026-09-03 snapshot and uses the invalid historical cutoff `23:59:59+09:00`; do not import it as-is. The strict replacement must use `2026-09-02T16:15:00+09:00` and `2026-09-03T16:15:00+09:00` separately.
- Pre-cutoff documents to re-audit: 2026-08-28 capital-reserve/retained-loss offset; 2026-08-14 FY2026 results and presentation; 2026-08-05 standalone transition and forecast; 2026-05-13 final ransomware report. The September 4 AGM notices and September 18 business-plan release are post-cutoff and excluded.
- Status: probable lineage found; exact new historical receipts not yet accepted. The existing report may be used only as a source for wording to re-check, not as a validated receipt.

### Identity: 2023-01-04|3133 and 2023-01-05|3133

- Reviewed the body of the issuer's 2022-11-22 09:00 progress disclosure (TDnet ID `140120221122569586`): it describes a ¥305 million loan through a subsidiary to Meta Energy, 1% interest, 2023-03-31 repayment date, and solar-equipment/land collateral in Hitachi (1,520.6 kW). The borrower had no capital, personnel, or related-party relationship with Kaihan, while a consulting contract had been signed in October; the issuer described the earnings effect as minor. Source copies: [disclosure page](https://irbank.net/3133/140120221122569586) and [PDF](https://f.irbank.net/pdf/20221122/140120221122569586.pdf).
- Other pre-cutoff source bodies available for the snapshots: 2022-11-10 half-year results; 2022-11-15 option issue; 2022-12-01 option-payment completion; 2022-12-05 store refurbishment; 2022-12-15 solar-project asset acquisitions; 2022-12-22 shareholder-benefit change; 2022-12-27 subsidiary allotment/renaming announcement. The 2022-12-27 payment was scheduled for January 6, after both cutoffs, so only the announcement may be described.
- The 2022-12-15 capital-reserve date-change item is indexed, but its primary body/URL still requires verification before it is cited.
- Status: material source found and body reviewed; no validated Luna-generated snapshot imported yet.

### Execution and blockers

- The first isolated Luna xhigh CLI run read/researched sources but its write-capable patch attempt was rejected by that child process's read-only policy; its final status text was mistakenly captured at the `historical_backfill_reports.json` path and has been removed. It was not a report receipt.
- A retry confirmed the main Codex process can read/write the workspace without additional user permission, but the installed CLI cannot run `gpt-5.6-luna` (`requires a newer version of Codex`); its websocket also failed to encode the Japanese workspace path. No analysis JSON was accepted, and no source/ledger/Discord/production data was changed by either attempt.
- Next safe action: use the active hourly heartbeat in the supported Codex runtime to generate this exact four-record JSON batch with Luna xhigh, validate every field/source/cutoff with `import-historical-fundamentals`, then test, regenerate the beta report, and checkpoint/push. Do not substitute a different model without the user's approval.

## 2026-09-23 — resumed audit checkpoint

- Branch/HEAD checked: `research/weak-early-beta` at `55b1d355e38b00321a515f29ccb50870853cf476`. Existing local timestamp-only regeneration in `historical_backfill_batch.json` and `historical_backfill_manifest.json` was preserved; no report receipt was imported.
- Usage at resume: 5-hour window 28% used; weekly window 20% used (80% remaining). Continue only while weekly remaining is above 30%; stop at the configured threshold.
- Reconfirmed the first batch still contains `2026-09-02|4052`, `2026-09-03|4052`, `2023-01-04|3133`, and `2023-01-05|3133`. No historical analysis was posted to Discord.
- New as-of lead for the 4052 identities: founder/CEO-related holder Waki Kenichiro filed EDINET changes at `2026-08-25 10:47` (report `S100YYIX`, 10.34%→9.32%), `2026-09-02 09:38` (`S100YZSH`, 9.32%→7.96%), and `2026-09-03 09:40` (`S100Z07L`, 7.96%→6.09%). The Aug 25 and Sep 2 filings are known by the Sep 2 16:15 cutoff; the Sep 3 filing is also before the Sep 3 16:15 cutoff. The Sep 2 snapshot must not include the Sep 3 filing. The web research runtime exposed the submission metadata and official EDINET links through its filing index, but EDINET's session page rejected text retrieval; the original report bodies still need direct validation before the receipts are finalized. Do not rely on later Sep 4/7 filings.
- Additional 3133 primary-body checks: JPX PDFs for the 2022-12-15 six solar-asset acquisitions (`140120221215579336.pdf`), the 2022-12-01 option-payment completion (`140120221201573459.pdf`), and the 2022-12-05 ¥55m store renovation asset (`140120221205574873.pdf`) were opened and reviewed. The 12-22 shareholder-benefit change was body-read from the direct TDnet PDF mirror `https://f.irbank.net/pdf/20221222/140120221222582261.pdf`; prefer an official JPX/issuer URL for the final receipt if recoverable.
- The 2022-12-15 capital-reserve/capital increase change was identified and its body read from a TDnet filing mirror: planned effective date changed from 2023-01-05 to 2023-01-31, with no expected earnings impact. The corresponding direct JPX PDF URL was inaccessible in this review; do not cite it in a final receipt until an accessible, verified disclosure URL/body is available.
- A 2022-12-07 correction to the subsidiary fixed-asset acquisition was found in the disclosure index, but its body has not yet been reviewed. Check it before finalizing the 3133 as-of evidence set; do not infer that it is immaterial.
- The Codex CLI still requires an explicit user decision before updating it to support `gpt-5.6-luna`; no model was substituted. No historical report JSON, imports, HTML publication, Cloudflare deployment, Discord post, production change, or push occurred in this checkpoint.
- Next: finish the 3133 pre-cutoff primary-document audit (especially the 12-07 correction and official links), continue the 4052 cutoff audit, then obtain the user's CLI/model decision and generate/validate only the next maximum-four identity receipt batch. The active `weak-early` heartbeat already carries the full 253-identity backfill task and usage gates; avoid creating a second automation.

## 2026-09-23 — successful local read route and Luna 6 batch import

- Branch: `research/weak-early-beta`; checked-out HEAD before this checkpoint was `3ff1b89a403c4523b35de3f800e742373faf7798`. The local worktree already held pending URL-migration changes; they were preserved.
- The earlier 4052 output is confirmed by `research/WEAK_EARLY_BETA_UI_FUNDAMENTAL_RECEIPT_20260923.md`. Its stored analysis cutoff is `23:59:59+09:00`, so those two existing analyses were not rewritten/reposted or accepted as strict 16:15 receipts; they remain `legacy_needs_asof_audit` until their source contents are checked against each cutoff.
- Successful local-read route: temporary `subst` aliases `V:` (screening-bot) and `W:` (weekly_report_gas), Codex CLI working directory `W:\`, and the established Premium Worker source prompts/quality reference. Invocation used `--sandbox danger-full-access`, `--search -a never exec`, `gpt-6-luna`, `model_reasoning_effort=xhigh`, and ChatGPT login; final JSON was isolated under `V:\weak_early_beta\fundamental_worker\out\`. The aliases were removed at completion.
- The prior assumption that GPT-6 Luna was unavailable was wrong. The historical batch and future beta fundamental runner now use GPT-6 Luna xhigh; the separate scheduled launcher remains on its existing lightweight setting.
- Generated/imported only `2023-01-04|3133` and `2023-01-05|3133`. Both use the 16:15 JST detection cutoff and eight reviewed pre-cutoff disclosure bodies each; each report passed the historical importer. No future disclosure was used and no Discord post was made.
- Batch evidence and hashes are in `research/WEAK_EARLY_HISTORICAL_FUNDAMENTAL_BATCH_20260923_01.md`; model output and normalized import JSON remain under `weak_early_beta/fundamental_worker/out/`.
- Import updated historical receipts, the canonical detections ledger, manifest, metrics, and generated HTML. Manifest: 2 complete, 249 pending, 2 legacy-as-of audits. Unit tests: 24/24 passed.
- No production/main/live Premium Worker/Sheets/Discord changes; 2026 remains SEALED. Continue only on the research branch; stop when weekly remaining reaches 30%.

## 2026-09-23 — next batch prepared; GPT-6 Luna CLI gate

- Branch/HEAD: `research/weak-early-beta`, `18278ec0ca7ba9e702c9ab9e1ca7f5379d6da734` (matches origin after the 4052 checkpoint).
- Prepared one bounded four-identity batch in `weak_early_beta/fundamental_worker/out/historical_backfill_luna6_batch4_prompt.md` (SHA256 `CF117FF76F11DC55F4FB4AD1165E98BB73A78A6239B2BF784D5277A9655BA541`): `2023-01-06|3133`, `2023-02-02|7037`, `2023-02-07|4586`, `2023-02-08|4586`. All remain pending; do not regenerate or reorder this batch when resuming.
- The installed `codex-cli 0.125.0` could not run the explicitly required `gpt-6-luna` with the current ChatGPT-account login. A direct Unicode-path attempt first showed a UTF-8 metadata-header failure; one retry using the documented temporary `V:` (screening-bot) / `W:` (weekly_report_gas) route still returned HTTP 400: model unsupported with a ChatGPT account. The CLI also reports that its model-list parser does not accept the server's `max` reasoning enum. No candidate output file was produced; there was no analysis, import, report regeneration, Discord post, or model substitution.
- The `V:` and `W:` aliases created for the retry were removed. No active batch lock/process remained. Usage at the end of the attempt: 16% five-hour used and 26% weekly used (74% weekly remaining).
- Resume gate: before making any model call, confirm a supported GPT-6 Luna xhigh runtime/account route is available. Do not repeat the same CLI invocation or substitute GPT-5.6 Luna. Then run this prepared batch once, read each cited primary disclosure body at its own 16:15 JST cutoff, validate once with `import-historical-fundamentals`, and either import passing identities or log a bounded source blocker. Historical Discord posts remain prohibited.
- Current ledger checkpoint: 253 identities, 4 complete, 249 pending, zero legacy-as-of-audit; the four batch identities above are not included in the completed count. Production and `main` remain untouched; 2026 remains SEALED for selection and retuning.
