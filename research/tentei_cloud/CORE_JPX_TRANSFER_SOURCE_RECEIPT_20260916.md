# JPX segment-transfer exact-byte receipt — 2026-09-16

Status: PASS_EXACT_BYTE_CAPTURE.

Research-only workflow run 35007416840 completed successfully at source commit 7457709559f35f7cae1c2488998bcbeae0d37083. Immutable artifact 10411777912 has digest `sha256:2d1b761e51a8cd70ba8501a5c1ed0df8a09ad4b17fa5456483967108728df7e7`.

Pinned transfer sources from the artifact receipt:
- current: HTTP 200, 51064 bytes, SHA-256 `85be65e0669f7a54891de41616715a5cebcc6d291f000487720ac1d067d53a2a`
- 2025: HTTP 200, 42369 bytes, SHA-256 `ade2457928577e98849ac23dfb5779ea14600d4bb7d89d5a87f377b121319145`
- 2024: HTTP 200, 28662 bytes, SHA-256 `dcd590122107f5632d4880b3d58ab38605f0b5bd11e6df51a90c9d56d3c35f71`

This passes segment-transfer source byte provenance only. PIT membership remains FAIL-CLOSED pending deterministic transfer ledger, row-level 375-vs-395 listing/delisting audit, and conflict-checked corrected reverse replay.
