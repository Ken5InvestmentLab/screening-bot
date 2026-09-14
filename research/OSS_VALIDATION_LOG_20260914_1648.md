# OSS/Validation log — 2026-09-14 16:48 JST

## Cross-lane scan

- Canonical/Event HEAD: `480bc9b5b62270f13f7e7de0accda008e6757bf9` — matches STATE processed SHA; no duplicate V20 work.
- Core HEAD: `7d19533560a186ffd4dceccb72fbaf1bd54117cc` — matches STATE processed SHA; rejected families remain closed and Cloud n=63/+9.86% work remains forensic-only.
- Consensus HEAD: `01299302461872a748693313e4de9c63cdcd32b8` — matches STATE processed SHA; preserved raw seed audit is already processed, retry `34810592135` remains owned by Consensus.
- OSS starting HEAD: `0837d299eff60698d0e2ec36c659a36bbc078542` — matched STATE processed SHA before this run.

No unprocessed cross-lane SHA required duplicate experimentation.

## OSS progress

The EDINET path was blocked from real acquisition because no external EDINET API key is available in this runtime. Instead of opening outcomes or inventing data, the next outcome-blind boundary was implemented:

- added `tvfree_screener/edinet_selected_zip_freeze.py`;
- added fail-closed tests in `test_edinet_selected_zip_freeze.py`;
- updated isolated OSS CI to cover both files;
- added `research/EDINET_SELECTED_ZIP_FREEZE_SPEC_20260914.md`.

The freeze helper consumes only the already-frozen sample receipt and exact selected ZIP files. It rejects missing/extra files, duplicate IDs, invalid/corrupt/empty ZIPs, or a receipt that no longer explicitly seals strategy outcomes and the no-replacement rule. For accepted bytes it records per-doc SHA256, byte size, member list, and a deterministic aggregate digest while keeping parser outputs unopened.

## CI

Action `34819456421` completed **SUCCESS**. The isolated OSS pytest step and existing custom EDINET synthetic self-check both passed.

## Outcome discipline

- real 2023-2025 metadata bytes: unopened / not acquired;
- selected real doc IDs: unopened / not frozen;
- real selected ZIP bytes: unopened / not frozen;
- custom-vs-edinet-tools real parser comparison: unopened;
- strategy performance and 2026 outcomes: unopened.

## Next safe action

1. Acquire complete 2023-2025 EDINET daily metadata with an external API key.
2. Freeze the full-calendar snapshot/hash chain.
3. Run the preregistered selector exactly once and freeze selected doc IDs.
4. Materialize selected ZIPs, run the new exact-byte freeze receipt, then feed those same digests to both parsers.
5. Record parser disagreements as audit findings; do not replace documents or select a parser based on downstream returns.
