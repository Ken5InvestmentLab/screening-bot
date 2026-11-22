"""A later validated Yahoo bar can settle only its original open."""

import json
import math

import pandas as pd

from .files import digest, encode
from .monitor import valid


def _restricted(intervals, entry, due):
    return any(interval["start"] <= due and (not interval.get("end") or interval["end"] > entry)
               for interval in intervals)


def _receipt(row, new_anchor, old_anchor, as_of, source_hash):
    if not all(valid(bar, True) for bar in (row, new_anchor, old_anchor)):
        return None
    if (row["high"] == row["low"] or row["volume"] <= 0 or row["actual_volume"] <= 0
            or not math.isclose(old_anchor["actual_close"], new_anchor["actual_close"], rel_tol=0, abs_tol=1e-8)):
        return None
    scale = old_anchor["close"] / new_anchor["close"]
    factor = scale * row["close"] / row["actual_close"]
    opening = row["actual_open"]
    if not all(math.isfinite(value) and value > 0 for value in (factor, opening)):
        return None
    if not math.isclose(opening, row["open"] * row["actual_close"] / row["close"], rel_tol=1e-9, abs_tol=1e-8):
        return None
    return {
        "price": {"open": opening, "factor": factor, "observed_after": as_of},
        "nominal_anchor_close": old_anchor["actual_close"],
        "source_sha256": source_hash,
    }


def recover_scheduled_exits(pipeline, source, calendar, intents, quote, *, frozen_end, as_of,
                            restrictions, identity_unverified_before, source_hash):
    """Pin the first usable receipt while leaving observed OHLC and the monitor alone."""
    index = {day: i for i, day in enumerate(calendar)}
    gaps = pipeline.missing_quote_days()
    eligible = set()
    for intent in intents:
        symbol = intent["symbol"]
        entry = index[intent["trigger_date"]] + 1
        for offset in (4, 7):
            if entry + offset >= len(calendar) - 1:
                continue
            due = calendar[entry + offset]
            key = (symbol, due)
            if (due > frozen_end and key in gaps
                    and intent["candidate_date"] >= identity_unverified_before.get(symbol, "")
                    and not _restricted(restrictions.get(symbol, ()), calendar[entry], due)
                    and quote(symbol, due) is None):
                eligible.add(key)

    db = pipeline.db
    db.execute("""CREATE TABLE IF NOT EXISTS scheduled_exit_evidence (
        symbol TEXT NOT NULL, day TEXT NOT NULL, observed_after TEXT NOT NULL,
        receipt_json TEXT NOT NULL, receipt_hash TEXT NOT NULL, PRIMARY KEY(symbol, day))""")
    receipts = {}
    for symbol, day, raw, stored_hash in db.execute(
            "SELECT symbol, day, receipt_json, receipt_hash FROM scheduled_exit_evidence WHERE observed_after <= ?",
            (as_of,)):
        value = json.loads(raw)
        if digest(value) != stored_hash:
            raise ValueError("corrupt scheduled exit evidence")
        if (symbol, day) in gaps and frozen_end < day < as_of and quote(symbol, day) is None:
            receipts[symbol, day] = value

    pending = eligible - receipts.keys()
    if not pending:
        return receipts
    anchors = {(symbol, calendar[index[day] - 1]) for symbol, day in pending}
    required = pending | anchors
    symbols, days = (set(items) for items in zip(*required))
    frame = source.loc[source["symbol"].isin(symbols) & source["date"].isin(pd.to_datetime(sorted(days))),
                       ["symbol", "date", "open", "high", "low", "close", "volume", "actual_open",
                        "actual_close", "actual_volume", "split_factor", "source_usable"]]
    rows = {}
    for row in frame.to_dict("records"):
        key = (row.pop("symbol"), row.pop("date").date().isoformat())
        if key in required:
            if key in rows:
                raise ValueError("duplicate source row for scheduled exit")
            rows[key] = row
    with db:
        db.execute("BEGIN IMMEDIATE")
        for symbol, day in sorted(pending):
            anchor_day = calendar[index[day] - 1]
            result = _receipt(rows.get((symbol, day)), rows.get((symbol, anchor_day)),
                              quote(symbol, anchor_day), as_of, source_hash)
            if result:
                db.execute("INSERT OR IGNORE INTO scheduled_exit_evidence VALUES (?, ?, ?, ?, ?)",
                           (symbol, day, as_of, encode(result), digest(result)))
                raw, stored_hash = db.execute(
                    """SELECT receipt_json, receipt_hash FROM scheduled_exit_evidence
                    WHERE symbol = ? AND day = ? AND observed_after <= ?""", (symbol, day, as_of)
                ).fetchone() or (None, None)
                if raw is not None:
                    value = json.loads(raw)
                    if digest(value) != stored_hash:
                        raise ValueError("corrupt scheduled exit evidence")
                    receipts[symbol, day] = value
    return receipts
