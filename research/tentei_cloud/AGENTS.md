# Tentei Cloud research

- Keep this research branch separate from production `main`, production workflows, Discord, Spreadsheet, TradingView, Stable, Sniper, and Mega. Do not merge research output into `main` without an explicit request.
- The ordinary 1H fetch universe comes from `jpx_universe.py` and the latest discovered JPX listed-issues workbook: Prime, Standard, and Growth domestic ordinary shares. Apply price and liquidity gates after raw 1H acquisition. `symbols_4h_universe.txt` is historical comparison evidence only.
- Preserve fixed Core and Monster gates, features, model architecture, seeds, cooldown, fold dates, and thresholds in universe comparisons. Fit the Monster model on the pinned OLD training data and score both universe arms with the same fold models. Never tune on NEW outcomes.
- On an incomplete daily 1H acquisition, block that day's new detection. Settle previously detected 5BD positions independently from an exact-date actual daily close; record unresolved prices, and never generate intraday bars from daily data.
- Treat the current JPX snapshot as a retrospective historical universe, not point-in-time or survivorship-free coverage. Retain raw fetch failure JSON, coverage, missing-symbol lists, and run/artifact IDs with each comparison.
