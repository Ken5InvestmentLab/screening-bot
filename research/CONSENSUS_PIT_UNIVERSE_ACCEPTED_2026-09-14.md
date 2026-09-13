# Consensus PIT universe replay accepted receipt — 2026-09-14

Research-only. No strategy returns or model scores were opened.

## Authoritative replay
- workflow: Consensus PIT Universe Replay
- run: **34771221050**
- artifact: `consensus-pit-universe-34771221050`
- artifact id: **10321434551**
- artifact digest: `sha256:74ab4c864ee8bfe0329b6fbaf9d29ff17d4507af964b91794fa26bf57d65c49a`
- source method: exact run80 `point_in_time_universe.py` reversal logic, with archive-discovery compatibility only.

## Acceptance
- event rows: 1,095
- listings: 632
- delistings: 463
- unknown market rows: **0**
- same-day code collisions: **0**
- valid_for_membership_reconstruction: **true**
- remaining unknown rows: **0**

Decision: **ACCEPTED_FOR_RESEARCH_MEMBERSHIP_RECONSTRUCTION**.

## Selected point-in-time membership checkpoints

| date | PIT domestic-common members | delta vs 2026-09-11 anchor (3,700) |
|---|---:|---:|
| 2024-10-01 | 3,818 | +118 |
| 2025-01-01 | **3,827** | **+127** |
| 2025-07-01 | 3,798 | +98 |
| 2026-01-01 | 3,775 | +75 |
| 2026-09-01 | 3,700 | 0 |

This confirms the run80 current-listed universe omitted historical members that had delisted by the 2026-09-11 anchor date.

## Relationship to price policy

PIT membership is common to both clean V47 price-policy arms:
- NOCAP: no absolute prior-close ceiling;
- CAP1000_PIT: PIT nominal prior close <= JPY 1,000.

The JPY1,000 ceiling is **not mandatory**. It remains only if the clean performance-first comparison demonstrates better locked performance.

## Remaining dependency

Membership reconstruction does not provide historical OHLCV/intraday bars for the restored delisted names. Coverage must be measured and fail-closed before a clean promotion claim.

V46 split-event/PIT nominal-price reconstruction remains mandatory even for NOCAP because `log_price` and other absolute-price semantics must not contain future split information.
