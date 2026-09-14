# Core canonical endpoint provenance contract — 2026-09-14 23:30 JST

## Purpose

Freeze an outcome-blind, fail-closed provenance contract before any new Core canonical relabeling. This does not reopen any rejected Core family and does not change candidate selection, thresholds, cooldown, entry/exit policy, or ranking. Cloud Monster exact replay remains closed absent genuinely contemporaneous identity-critical evidence.

## Immutable research policy

- New performance calculations in this lane use transaction cost **0% only**.
- Win = gross return > 0.
- Canonical endpoint = next XTKS session open -> fifth XTKS session close, with entry session counted as holding session 1.
- 2026 outcome is report-only.
- Legacy 0.5%/1% evidence is archival only and cannot drive a new ranking or GO/NO-GO.

## Pinned calendar manifest

A canonical relabeling run MUST receive an explicit vendor-specific XTKS endpoint manifest with exactly these identity columns:

- `date` — XTKS session date, strict ascending order, unique.
- `calendar_name` — must equal `XTKS` for every row.
- `calendar_version` — nonblank and constant for the manifest.
- `open_bar_ts` — exact raw-vendor timestamp whose `open` is the official session-opening endpoint used by this dataset.
- `close_bar_ts` — exact raw-vendor timestamp whose `close` is the official session-closing endpoint used by this dataset.

The canonicalized manifest is bound by SHA-256. Any date/order/timestamp/version change changes the receipt and MUST fail verification against the frozen expected hash.

This intentionally separates exchange-session identity from data-vendor bar semantics. The evaluator must not infer endpoint timestamps from `first()`/`last()` observed rows.

## Fail-closed endpoint rules

For every frozen candidate row:

1. signal date must exist in the pinned manifest;
2. entry date is manifest position `signal + 1`;
3. exit date is manifest position `signal + 5`;
4. the candidate symbol must have exactly one raw row at the manifest `open_bar_ts` for entry;
5. the candidate symbol must have exactly one raw row at the manifest `close_bar_ts` for exit;
6. entry `open` and exit `close` must be finite and positive;
7. no observed-date shifting and no first/last-available-row fallback are allowed.

If any selected row fails the endpoint contract, the provenance receipt is `FAIL_CLOSED`; performance from that run is not formal comparable evidence.

## Receipt fields

The endpoint provenance primitive records at least:

- status `PASS` / `FAIL_CLOSED`;
- calendar name/version/hash;
- candidate/resolved/unresolved counts;
- cost fixed to 0%;
- win definition;
- endpoint definition;
- explicit `fallback_to_observed_date_or_row = false`.

A later wiring step should additionally persist source run/artifact identity/hash alongside this calendar receipt before any canonical performance output is accepted.

## Implementation frozen this pass

`research/tentei_cloud/endpoint_provenance.py` implements manifest canonicalization/hash verification and exact-timestamp endpoint resolution. `research/tentei_cloud/test_endpoint_provenance.py` covers:

- next-open/fifth-close mapping across a non-session gap;
- missing exact close endpoint failing closed even when a nearby row exists;
- calendar hash tampering rejection;
- duplicate endpoint-row rejection;
- unsorted calendar rejection.

No strategy outcome was recomputed in this pass. The existing `audit_core_canonical_endpoint.py` is not yet wired to this primitive, so formal relabeling remains blocked until a real pinned XTKS/vendor manifest and source artifact receipt are supplied and the evaluator consumes them.
