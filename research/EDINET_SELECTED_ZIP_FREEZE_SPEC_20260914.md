# EDINET selected ZIP freeze spec — 2026-09-14

Scope: research-only OSS/Validation lane. No production/main changes.

## Purpose

Freeze the exact document bytes that will later be passed to both the custom EDINET parser and `edinet-tools`, before either parser output is opened. This prevents parser-aware file substitution, retry-biased replacement, or comparing different source bytes.

## Inputs

- the preregistered real-sample receipt emitted by `edinet_oss_sample_selector.py`;
- one local ZIP named `<doc_id>.zip` for every frozen `selected_doc_ids` entry;
- no accounting values, parser outputs, strategy returns, ranks, labels, model scores, or 2026 market outcomes.

## Fail-closed rules

1. `selected_doc_ids` must be non-empty, unique strings.
2. The sample receipt must explicitly retain `strategy_outcomes_opened=false` and `no_replacement_rule=true`.
3. The ZIP directory must contain exactly the selected `<doc_id>.zip` set: missing files and extra ZIP/file drift both fail.
4. Every selected file must be a valid, non-empty ZIP and pass CRC/member integrity testing.
5. No selected document may be replaced because either parser later fails, misses a value, or disagrees.

## Frozen receipt

`tvfree_screener/edinet_selected_zip_freeze.py` emits, in original selected-doc order:

- doc ID;
- exact filename;
- SHA256 of raw ZIP bytes;
- byte size;
- sorted ZIP member names;
- a deterministic aggregate SHA256 chain over doc ID, per-file digest, and size.

The receipt explicitly records `strategy_outcomes_opened=false` and `parser_outputs_opened=false`.

## Next boundary

Only after the real 2023-2025 metadata snapshot and selector are frozen may selected ZIPs be materialized and passed through this freeze step. The custom parser and `edinet-tools` must then consume the exact SHA256-frozen bytes. Parser disagreement is an audit finding; neither side is chosen based on strategy outcomes.

## Verification

Synthetic fail-closed tests cover exact-set enforcement, missing/extra files, invalid ZIPs, duplicate doc IDs, and sealed-outcome/no-replacement receipt requirements. CI run `34819456421` is the authoritative test run for this boundary.
