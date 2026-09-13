# V47 PIT daily-volume eligibility delta — 2026-09-14

Outcome-free universe audit. No strategy returns/model scores used.

## Scope
Frozen run80 current-listed 3,700-symbol daily dataset only. This is a conservative data-semantics diagnostic before restored/delisted PIT members are added.

PIT reconstruction:
- PIT prior close = frozen prior close × cumulative future split factor;
- PIT prior volume = frozen prior volume ÷ cumulative future split factor.

## Volume gate only — prior volume >= 10,000 shares

2025:
- old present-basis volume-gate rows: 661,515
- PIT volume-gate rows: 654,762
- adjusted-only false positives: **6,783**
- PIT-only rows: 30
- adjusted-only fraction of old passing rows: **1.025%**
- affected false-positive symbols: 180

2025H1:
- old: 318,467
- PIT: 314,180
- adjusted-only: **4,316**
- PIT-only: 29
- adjusted-only fraction: **1.355%**
- affected symbols: 176

2025H2:
- old: 343,048
- PIT: 340,582
- adjusted-only: **2,467**
- PIT-only: 1
- adjusted-only fraction: **0.719%**
- affected symbols: 110

## Combined legacy CAP1000 price + volume eligibility

Old rule:
- split-adjusted prior close <= JPY1,000
- split-adjusted prior volume >= 10,000

Clean PIT rule:
- PIT nominal prior close <= JPY1,000
- PIT prior share volume >= 10,000

2025:
- old eligible rows: 254,541
- clean PIT eligible rows: 235,566
- old-only false positives: **19,127**
- PIT-only additions: 152
- old-only fraction of old eligible: **7.514%**
- affected old-only symbols: 205

2025H1:
- old: 130,235
- clean PIT: 117,401
- old-only: **12,930**
- PIT-only: 96
- old-only fraction: **9.928%**

2025H2:
- old: 124,306
- clean PIT: 118,165
- old-only: **6,197**
- PIT-only: 56
- old-only fraction: **4.985%**

## NOCAP consequence

Removing the JPY1,000 ceiling does **not** remove all split leakage by itself because the historical prior-volume gate is also affected.

For clean NOCAP the PIT prior-volume correction remains mandatory.

## Limitations
- This count is inside the frozen current-listed 3,700-symbol survivor universe only.
- Accepted PIT membership adds restored/delisted historical names separately.
- No strategy performance was inspected.

Production modified: false.
