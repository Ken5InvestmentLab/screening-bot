# CMF local label coverage audit

- Scope: frozen 2022H2/2023 selected rows only; cached local OHLCV; no network and no later-period values.
- Canonical label-cache rows absent: 13 / 1800.
- Rebuilt statuses for absent rows: `{"RESOLVED": 13}`.
- Existing cached labels match local rebuild: `{"entry_date": true, "entry_price": true, "exit_date": true, "exit_price": true, "gross_return": true, "label_resolved": true, "label_status": true}`.
- Returns use an assumed 0.5% round-trip cost. Rebuilding labels only diagnoses coverage; it does not retune or promote the rejected CMF rule.

| Period | Requested | Cached resolved | Rebuilt resolved | Cached mean | Rebuilt mean | Cached median | Rebuilt median |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2022H2 | 595 | 587 | 589 | -0.9344% | -0.9541% | -0.8356% | -0.8559% |
| 2023 | 1205 | 1181 | 1192 | -0.2862% | -0.2496% | -0.7132% | -0.7065% |
