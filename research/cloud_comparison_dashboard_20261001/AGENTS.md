# Cloud comparison dashboard

- Edit the renderer sources and regenerate `index.html` / `manifest.json`; do not patch the embedded result data manually. Keep the dashboard usable as a standalone offline HTML file.
- Preserve the folder's LF line endings. Aggregate source hashes normalize CRLF to LF; production-state immutability checks hash the original bytes.
- Normalize units at the CSV boundary: cap returns/rates are fractions, exit metrics are already percentages. Keep the five-day cohort separate from the twenty-endpoint common cohort.
- Treat `production_reference.json` as a frozen, read-only comparison snapshot. A price-cap match alone does not establish production equivalence: verify detection identities, model/input provenance and return contracts before describing a research delta as a production improvement.
- The normal generator must not read or change production state. Explicit production audits may read the saved ledger and metrics, must verify unchanged hashes, and must not run detection, learning, notifications or deployment.
