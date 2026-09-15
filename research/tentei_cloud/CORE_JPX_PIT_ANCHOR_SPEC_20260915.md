# Core JPX PIT anchor/replay contract — 2026-09-15

Status: FROZEN RESEARCH CONTRACT; performance unopened.

1. Anchor must be an official JPX TSE-listed-issues object whose publication page and workbook bytes are both SHA-256 pinned.
2. The workbook effective/as-of date must be recorded explicitly. A current or month-end anchor is acceptable if the frozen official listing/delisting ledger spans the reverse-replay interval back to `2024-09-17` without gaps.
3. Membership reconstruction is deterministic set replay only: reverse LISTING removes the issue; reverse DELISTING restores the issue. Forward replay uses the inverse operations.
4. Identity is keyed by JPX/TSE issue code plus source fields needed to disambiguate non-common-stock products. Product/market eligibility filters must be frozen before any performance is opened.
5. Duplicate same-direction events may be normalized only when source-identical; contradictory identity/status events are quarantined and PIT remains fail-closed until resolved.
6. The output receipt must pin anchor SHA, event-ledger SHA (`5babf8d153f243e4be3bab6c8ef2c0f45ff773ca744917329cd97f551788ff28`), replay direction/range, conflict count, per-date membership counts, normalized membership object SHA, and parser version/commit.
7. Do not infer listing existence from Yahoo first/last observations or generate `membership × XTKS × hour` Cartesian expected keys from PIT alone.
8. Only after PIT membership PASS may the lane freeze independent exact-hour activity evidence and produce the one-shot missing inventory.
9. No strategy retune or performance selection is allowed in this provenance stage. Any later new performance uses cost 0%; win = gross return > 0; 2026 is report-only.
