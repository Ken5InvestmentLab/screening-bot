# Ledger reconciliation checker verification — 2026-09-14 JST

## Purpose

Keep the shared `EXPERIMENT_LEDGER.md` safe while multiple research chats commit to the same branch. The GitHub contents API replaces whole-file contents, so a stale or truncated read can overwrite another lane's entries. This checker is deliberately read-only.

## Added

- `ledger_reconcile_check.py`
  - extracts `## <experiment-id> — <status>` headings from the current ledger and a pending-append file;
  - reports pending, present, and missing experiment IDs;
  - marks the pending file deletable only when every pending ID is already represented in the ledger;
  - never mutates either input file.
- `test_ledger_reconcile_check.py`
  - heading-ID extraction;
  - partial reconciliation detection;
  - complete reconciliation detection;
  - empty-pending guard.

## Verification

Local functional verification: **4/4 PASS**.

Cases checked:
1. status text is excluded from the experiment ID;
2. a partially merged pending file reports only the missing IDs;
3. complete reconciliation sets `safe_to_delete_pending_file=true`;
4. an empty pending file is never treated as safely deletable.

## Current ledger policy

The shadow-lane entries remain in `reports/ledger_pending_shadow_lane_20260914.md` until a byte-safe full ledger read/append/rebase path is available. Do not force-update or reconstruct the shared ledger from a truncated connector response.

## Production impact

None. Research-only files under `tvfree_screener/batch02`; no Discord, Sheets, TradingView, production workflow, Stable, Sniper, or Mega modifications.
