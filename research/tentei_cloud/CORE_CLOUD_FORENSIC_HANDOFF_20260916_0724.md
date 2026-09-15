# Core + Cloud forensic handoff — 2026-09-16 07:24 JST

Core24 PIT membership remains frozen and unchanged. The final exact-hour activity blocker is now narrowed to a concrete official source: JPX/JPXI **FLEX Historical / Historical Real-Time Market Data (Including Tick Data)**.

The official service has the required semantics to witness actual cash-equity executions independently of Yahoo raw1H, including timestamped historical real-time data. Adoption state is `SEMANTIC_SOURCE_IDENTIFIED_ACCESS_NOT_ACQUIRED`: it is paid/contract access and no raw FLEX bytes are present in the evidence chain.

Next P0: acquire/pin FLEX Historical bytes (or another source meeting the same exact execution-level contract), bind source SHA/spec/parser, derive unique activity keys, then and only then generate formal expected keys and run missing inventory once. Until acquisition, formal completeness/performance remains sealed.

Cloud Monster remains `HISTORICAL_EXACT_REPRO_UNAVAILABLE`; no guessing, retune, costed performance, or production changes.
