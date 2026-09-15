# Consensus V47 corrected midterm H1 — 2026-09-15

Classification: `MIDTERM_DIAGNOSTIC_NOT_PROMOTION_EVIDENCE`.

This result is diagnostic only. Formal raw1H acceptance remains NOT PASSED and promotion H1/H2 remain unopened. The frozen V11/min/0.95/guard-none/both-sessions/strict5/no-replacement contract, canonical next-XTKS-open -> D+5 close endpoint, and cost 0% were unchanged. Missing raw pairs were not interpolated or synthesized. Core24 nominal OHLC was first deterministically normalized according to the frozen price-basis correction; raw 1H volume was unchanged.

Source diagnostic run: `34943802848` (SUCCESS). Artifact digest: `sha256:e22b84ce4d9f10872060fabfc6af1f7636e62077c4b03298b46237ae587d0c9b`.

## H1 corrected diagnostic

Period: 2025-01-06 .. 2025-06-30. Endpoint: next official XTKS open -> D+5 close. Cost: 0%. Win: gross canonical return > 0.

| arm | coverage | n | mean | median | win | +10 | +20 | +50 | -10 | -20 | Top1-ex | Top3-ex |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| NOCAP | 35.3898% | 43 | +1.3817% | -0.7375% | 39.53% | 18.60% | 13.95% | 0.00% | 11.63% | 4.65% | +0.2759% | -1.0890% |
| CAP1000_PIT | 83.1124% | 41 | +1.7117% | -2.0305% | 43.90% | 14.63% | 7.32% | 2.44% | 9.76% | 0.00% | +0.2878% | -1.3069% |

Coverage caveat: partial preserved Yahoo seed only. NOCAP 301,897 / 853,061 required pairs; monthly minimum 33.9002%; 2,592 completely missing required symbols; restored-pair coverage 0%. CAP1000_PIT 258,339 / 310,831; monthly minimum 77.3420%; 642 completely missing required symbols; restored-pair coverage 0%.

Under the unchanged H1 chooser, `CAP1000_PIT` is the corrected diagnostic H1 leader. This does not make it promotion evidence. H1 is now opened/not untouched. Same-family retuning and additional price-cap search remain forbidden.

The prior H2 NOCAP opening was selected from an invalid source-price-basis H1 and must not be used for current ranking. Any corrected H2 diagnostic must open only `CAP1000_PIT`, with the same frozen contract and corrected source normalization. CAP1000_PIT H2 is still unopened at this receipt.
