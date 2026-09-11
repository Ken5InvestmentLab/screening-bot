# 天底極致 Cloud — 1H Research

Research branch only. No production Discord, Sheets, or main-branch writes.

## Goal

Compare genuine Yahoo Finance JPX 1h bars against the current 4H/session implementation.

Primary questions:

1. Can Monster signals be detected earlier than the current 4H/session trigger?
2. Does 1H improve Monster recall without exploding false positives?
3. Does 1H help Core, or is 4H + daily state already better for stability?
4. Is the best architecture 1H trigger + 4H confirmation + daily regime?

## Raw data

Use `research/cloud_1h_fetch.py`.

Example:

```bash
python research/cloud_1h_fetch.py \
  --symbols 6085,4052,8105,3444,5575,6666,2338 \
  --start 2026-03-01 \
  --end 2026-09-10 \
  --out research/output/cloud_1h_monsters.csv
```

The script keeps genuine 1h bars and does not aggregate them into the production 09:00 / 13:00 session bars.

## Evaluation rules

- Use JPX trading calendar for 5BD labels.
- Do not count missing bars as trading days.
- De-duplicate by `(symbol, timestamp)`.
- Treat 15:30/16:00 zero-volume flat rows as closing snapshots, not normal 1h candles.
- Train/validation selection must not use the future holdout.
- August 2026 is already opened and must not be called untouched holdout.
- Preserve Monster tail capture; do not optimize only robust mean.
- Production/main remains unchanged until explicit Go.

## Current visible lanes

- **Core** — everyday stable lane.
- **Monster Watch** — top ~30% of the Monster candidate pool; dashboard/watchlist.
- **Monster Prime** — top ~10%; push-notification class.

Internal A/B labels may remain in research code but should not be user-facing.
