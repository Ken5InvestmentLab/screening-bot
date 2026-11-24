# Reviewed issuer companion documents

The original `PREMIUM_LEGACY_WORKER.mjs` remains the byte-for-byte Premium
snapshot (SHA-256 `98edbc6921dfcad6b853660a1d1bc6e508ef684f71d29732960330a53cb80dc3`).
`PREMIUM_CLOUD_WORKER.mjs` uses that source with the two narrowly scoped
quality corrections below. All research, full-batch checks and no-send behavior
remain the same. Do not remove a cited source or invent a time to pass a check.

- The official issuer IR news and library list
  `https://www.aiholdings.co.jp/uploads/2026/11/fy2027q1_presentation.pdf`
  on 2026-11-16, without a publication time. Its exact label is
  `2026-11-16 2027年6月期 第1四半期決算説明資料(時刻記載なし)`.
  Keep `publishedAtPrecision: "date_only"` and that date. The existing Cloud
  cutoff check still rejects a date-only disclosure on or after the cutoff day.
  A guessed hh:mm and a different date for this URL are rejected.
- The issuer's `https://www.aiholdings.co.jp/uploads/2026/09/Security-Report_20.pdf`
  is the 20th annual filing, dated 2026-09-25. Page 30 identifies the 2026-06-30
  period and records no applicable stock-option, other warrant or variable-price
  convertible-bond exercise items. This is dated capital-structure evidence,
  not the current earnings material and not proof of today's zero balance.
  Keep both current-quarter originals in the disclosure links. State
  `2026年6月末基準では新株予約権等は該当なし`, that the cutoff's current
  unexercised balance is unconfirmed, and that the past finding does not imply
  a current zero balance. The annual-only packet is still rejected.

Primary provenance, checked 2026-11-25 JST:

- https://www.aiholdings.co.jp/ir/news/
- https://www.aiholdings.co.jp/ir/library/
- https://www.aiholdings.co.jp/uploads/2026/11/fy2027q1_presentation.pdf
- https://www.aiholdings.co.jp/uploads/2026/09/Security-Report_20.pdf

Only the pending 3076 report needs re-review. Keep the validated 6908 and 9823
reports unchanged, retain the original three-alert claim and 11/24 cutoff, and
repeat the full three-report dry-run and direct-URL checks before import.
