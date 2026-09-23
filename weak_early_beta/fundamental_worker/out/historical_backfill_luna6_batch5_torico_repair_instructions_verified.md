# Luna 6 xhigh — TORICO historical report repair (verified evidence packet)

Generate exactly one report for `2023-03-15|7138` (ＴＯＲＩＣＯ), cutoff `2023-03-15T16:15:00+09:00`, using GPT-6 Luna (`gpt-6-luna`) with `xhigh` reasoning. Do not substitute a model. Do not use web search, browser/UI automation, or any network lookup: the parent agent has already checked source lists and read the primary documents listed below. Do not edit files; the invoking CLI will save your final message to `historical_backfill_candidate_luna6_batch5_torico_repair_raw.json`.

Read the canonical batch entry and existing candidate only to preserve identity, name, and selector names. Copy the exact five selectors from the candidate. Follow `premium-fundamental-snapshot` field-writing and disclosure-selection rules. The report must be concise, company-specific, non-advisory, and based only on the contemporaneous evidence below. Do not use later releases, prices, returns, or hindsight.

## Source-list audit already completed

- Official TORICO IR library: `https://www.torico-corp.com/ir/library/disclosure/`
- Official TORICO IR news list: `https://www.torico-corp.com/ir/news/`
- IRBANK disclosure list: `https://irbank.net/7138/ir`
- The list showed the February 13 Q3 results and presentation at 15:30, a presentation correction at 19:00, then the March 1 buyback-progress notice at 15:30. No later fundamentally material notice was listed through the March 15 cutoff.

## Primary-document bodies read

1. Q3 results, published `2023-02-13T15:30:00+09:00`, direct primary URL `https://www2.jpx.co.jp/disc/71380/140120230213507970.pdf`. Nine-month revenue ¥3,713.965m (-9.2% y/y), operating profit ¥92.157m (-47.3%), ordinary profit ¥90.439m (-50.4%), net profit ¥63.114m (-47.8%). Q3-quarter sales were +0.6% y/y; December EC sales exceeded ¥700m and were a record. Q3-quarter EC visitors were 9.9m (+10.0%); purchase conversion was 1.2%, down from 1.3% (-10.4% y/y), but improved from below 1% in H1. The full-year forecast remained unchanged.
2. Buyback progress, published `2023-03-01T15:30:00+09:00`, direct primary URL `https://www2.jpx.co.jp/disc/71380/140120230301521431.pdf`. Purchases during Feb 1–28: 9,900 shares for ¥10,626,100. Cumulative through Feb 28: 23,400 shares for ¥26,854,800. The Jan 12 authorization was up to 100,000 shares / ¥100m, market purchases through June 30. Treat this as a partial-progress update, not automatically positive.
3. The same-day Q3 presentation correction, published `2023-02-13T19:00:00+09:00`, URL `https://www2.jpx.co.jp/disc/71380/140120230213509395.pdf`, was read. It only fixed garbled numeric labels in a page-31 graph and explicitly said released financial-statement figures were unchanged. It is not fundamentally material and should be noted as assessed, but omitted from `disclosures` and `開示リンク`.

For the analysis, weigh the sharp nine-month revenue/profit declines and unchanged forecast against the December EC recovery and buyback progress. Do not describe a record month as proof of a sustained turnaround. The company operates manga full-volume e-commerce, digital comics, and manga/anime event/store services; avoid generic company descriptions.

Include only the two materially useful disclosures (Q3 results and March 1 buyback progress) in `disclosures` and `開示リンク`. Use exactly these 2–3 non-PDF listing pages in `Sources`: official IR library, official IR news, and IRBANK list. The combined `開示リンク` must remain under 1,000 characters, and every selected disclosure URL must match exactly. `sourceChecks` must contain `official_ir` and `irbank_or_tdnet` roles with the verified listing URLs and concise results. Every cited primary document must have `contentReviewed: true`.

Return only `{ "reports": [ <one report> ] }`, with exact identity/cutoff/selectors, the required seven fields in canonical order, `auditStatus: "pass"`, and an `auditNotes` sentence recording the assessed formatting-only correction. `材料インパクト` starts with an allowed Premium label plus `：`, and its substantiated sentence is at most 90 Japanese characters after the label. Historical reports are never sent to Discord.
