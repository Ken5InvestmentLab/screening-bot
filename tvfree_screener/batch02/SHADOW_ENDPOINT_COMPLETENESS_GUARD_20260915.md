# Prospective Shadow endpoint completeness guard — 2026-09-15

Status: **OUTCOME-BLIND DATA-INTEGRITY INFRASTRUCTURE / CI GREEN**

This change does not open strategy returns and is not promotion evidence.

## Purpose

Before prospective-shadow 5BD resolution is accepted, audit the frozen shadow selection ledger against the pinned XTKS calendar and daily endpoint dataset.

For each mature shadow row:

- entry endpoint must exist at the **next XTKS session open** for the same symbol;
- exit endpoint must exist at the **fifth XTKS session close** for the same symbol;
- the exact required price must be finite and strictly positive.

Fail closed on:

- missing required symbol/date/field endpoint pairs;
- a required symbol with no available endpoint row;
- non-finite or non-positive required open/close;
- duplicate pinned session-calendar dates;
- shadow `signal_date` outside the pinned session calendar.

Candidates that have not yet reached the fifth later XTKS session remain pending and do not fail completeness.

## Integrity contract

- strategy outcomes opened: **false**
- gross returns computed: **false**
- threshold/ranker/cooldown changes: **none**
- endpoint contract: next XTKS open -> fifth XTKS close
- production authorization: **false**

Implementation:

- `prospective_shadow_endpoint_completeness_guard.py`
- `test_prospective_shadow_endpoint_completeness_guard.py`
- CI wiring in `prospective-shadow-resolution-continuity-tests.yml`

Canonical HEAD implementing the boundary: `962a062bc8a46eb32df65cfa737676463ec3ea1a`.

CI run `34867054366`: **SUCCESS**.

## Next

Wire this audit into the verified resolve/write boundary so a successful resolution cannot be written unless endpoint completeness passes. Then pin the completeness result in an immutable receipt before accepting new resolved output.
