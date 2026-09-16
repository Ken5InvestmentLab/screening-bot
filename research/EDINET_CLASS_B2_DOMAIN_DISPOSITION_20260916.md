# EDINET Class B2 domain disposition — 2026-09-16 22:48 JST

## Scope
Research-only, outcome-blind disposition for the remaining Class B2 documents from the frozen same-ZIP crosscheck. No returns, strategy outcomes, thresholds, rankers, gates, periods, or endpoints were opened or changed.

Documents: `S100QF0X`, `S100RWZI`, `S100UXL5`.

## Frozen-byte evidence
The immutable pre-parser artifact `10385897929` was re-opened only for source semantics. Each of the three EDINET ZIPs contains a `jpsps070000-asr-001_<G-code>-000_...csv` cover/DEI file plus multiple numbered `jpsps070000-asr-001_<G-code>-00N_...csv` financial-statement files.

Observed component counts:
- S100QF0X / G04764: `-000` plus `-001`, `-002`, `-003`.
- S100RWZI / G14585: `-000` plus `-001`, `-002`, `-003`, `-004`.
- S100UXL5 / G14307: `-000` plus `-001`, `-003`, `-004`.

The `-000` files identify the filing as an investment-fund filing rather than one ordinary listed-company fundamental record. For example S100QF0X contains:
- `jpsps_cor:DocumentTitleCoverPage = 有価証券報告書`
- `jpdei_cor:FundCodeDEI = G04764`
- `jpsps_cor:FundNameCoverPage` listing three distinct funds
- `jpdei_cor:FundNameInJapaneseDEI` naming one fund
- issuer/filer = Daiwa Asset Management.

The numbered component files then carry the same standard current/prior non-consolidated contexts (`Assets`, `NetAssets`, `OperatingIncomeLoss`, `ProfitLoss`) for different fund components, with distinct values. The same multi-component pattern is present in S100RWZI and S100UXL5.

## Disposition
Class B2 is therefore **OUT_OF_DOMAIN_MULTI_FUND_FILING**, not a missing alias and not a context tie that should be broken by value/order heuristics.

For the corporate-fundamental crosscheck, a filing that exposes a fund-code / multi-fund `jpsps070000` structure MUST NOT be collapsed to one corporate assets/equity/operating-income/net-income row. It is fail-closed/excluded from corporate-fundamental comparability unless a future research task explicitly models fund-level identity.

Forbidden fixes:
- choose the first numbered G component merely by order;
- choose max/min/closest value;
- choose whichever component agrees with the OSS parser;
- merge components;
- use strategy returns/performance to select a component.

This closes the semantic cause of the remaining 3 docs / 9 rows without fabricating a filing-to-G-component mapping.

## Crosscheck status after disposition
The corrected same-ZIP run remains the frozen validation receipt: 44 comparable inputs before domain disposition, 41 all-match, 3 Class B2 multi-fund documents. Class C remains resolved by basis-aware mapping (`ProfitLoss -> net_income_total`). After applying the corporate-domain rule, the 3 Class B2 documents are not valid corporate-fundamental comparison units; they remain fail-closed rather than being counted as parser matches.

No performance was opened.
