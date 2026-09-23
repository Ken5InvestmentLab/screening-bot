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
