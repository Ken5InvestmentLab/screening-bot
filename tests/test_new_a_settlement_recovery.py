import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from weak_early_beta.new_a.bundle import FIELDS, prepare_bundle
from weak_early_beta.new_a.files import atomic_write, read
from weak_early_beta.new_a.settlement_recovery import recover_scheduled_exits


CALENDAR = [
    "2026-11-04", "2026-11-05", "2026-11-06", "2026-11-09", "2026-11-10", "2026-11-11",
    "2026-11-12", "2026-11-13", "2026-11-16", "2026-11-17", "2026-11-18",
]
SYMBOL = "1234"
DUE = CALENDAR[6]
ANCHOR = CALENDAR[5]
AS_OF = CALENDAR[-1]
INTENT = {"symbol": SYMBOL, "candidate_date": CALENDAR[0], "trigger_date": CALENDAR[1], "episode_id": 1,
          "support": 182, "resistance": 203, "priority_score": 1_000_000}


def bar(close=100, actual_close=200, actual_open=198):
    return {"open": actual_open * close / actual_close, "high": close * 1.02, "low": close * .97,
            "close": close, "volume": 20_000, "actual_open": actual_open, "actual_close": actual_close,
            "actual_volume": 10_000, "split_factor": actual_close / close, "source_usable": True}


class ScheduledExitRecovery(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.addCleanup(self.db.close)
        self.observed = {(SYMBOL, ANCHOR): bar(close=200)}
        self.gaps = {(SYMBOL, DUE)}
        self.pipeline = SimpleNamespace(db=self.db, missing_quote_days=lambda: self.gaps,
                                        observed_quotes=lambda: self.observed, all_events=lambda: [])
        self.quote = lambda symbol, day: self.observed.get((symbol, day))
        self.anchor = bar()
        self.due = bar(close=96, actual_close=96, actual_open=95)

    def frame(self, *, date=DUE, due=None, anchor=None):
        return pd.DataFrame([
            dict(symbol=SYMBOL, date=pd.Timestamp(ANCHOR), **(anchor or self.anchor)),
            dict(symbol=SYMBOL, date=pd.Timestamp(date), **(due or self.due)),
        ])

    def recover(self, frame=None, **kwargs):
        options = dict(frozen_end=CALENDAR[1], as_of=AS_OF, restrictions={},
                       identity_unverified_before={}, source_hash="a" * 64)
        options.update(kwargs)
        return recover_scheduled_exits(self.pipeline, self.frame() if frame is None else frame,
                                       [day for day in CALENDAR if day <= options["as_of"]],
                                       [INTENT], self.quote, **options)

    def test_exact_date_first_verified_receipt_remains_fixed(self):
        self.assertEqual(self.recover(self.frame(date=CALENDAR[7])), {})
        receipt = self.recover()
        self.assertEqual(receipt[(SYMBOL, DUE)]["price"], {"open": 95, "factor": 2, "observed_after": AS_OF})
        self.assertEqual(self.recover(self.frame(due=bar(actual_open=199)), source_hash="b" * 64), receipt)
        self.assertEqual(self.recover(restrictions={SYMBOL: [{"start": CALENDAR[3], "end": DUE}]}), receipt)
        self.assertEqual(self.recover(as_of=CALENDAR[-2]), {})
        self.assertEqual(set(self.observed), {(SYMBOL, ANCHOR)})

    def test_invalid_or_revised_source_never_settles(self):
        self.assertEqual(self.recover(self.frame(anchor=bar(actual_close=201))), {})
        self.assertEqual(self.recover(self.frame(due={**self.due, "source_usable": False})), {})
        self.assertEqual(self.recover(self.frame(due={**self.due, "volume": 0})), {})
        self.assertEqual(self.recover(self.frame(due={**self.due, "actual_open": 94})), {})
        self.assertEqual(self.recover(self.frame(due={**self.due, "high": 96, "low": 96})), {})
        self.assertEqual(self.recover(restrictions={SYMBOL: [{"start": CALENDAR[3], "end": DUE}]}), {})
        self.assertEqual(self.recover(identity_unverified_before={SYMBOL: CALENDAR[2]}), {})
        self.gaps.clear()
        self.assertEqual(self.recover(), {})

    def test_eighth_session_is_the_only_other_supported_due_date(self):
        self.gaps = {(SYMBOL, CALENDAR[9])}
        self.observed = {(SYMBOL, CALENDAR[8]): bar(close=200)}
        frame = pd.DataFrame([
            dict(symbol=SYMBOL, date=pd.Timestamp(CALENDAR[8]), **self.anchor),
            dict(symbol=SYMBOL, date=pd.Timestamp(CALENDAR[9]), **self.due),
        ])
        self.assertEqual(set(self.recover(frame)), {(SYMBOL, CALENDAR[9])})

    def test_bundle_keeps_recovery_out_of_the_ordinary_quote_slots(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            files = {key: root / f"{key}.json" for key in ("history_input", "presentation")}
            files["quotes"] = root / "quotes.sqlite"
            with closing(sqlite3.connect(files["quotes"])) as frozen:
                with frozen:
                    frozen.execute("CREATE TABLE quotes(symbol TEXT, date TEXT)")
            episode = {k: v for k, v in INTENT.items() if k != "trigger_date"}
            atomic_write(files["history_input"], {
                "calendar": CALENDAR[:2], "episodes": [episode], "intents": [INTENT],
                "watches": [{**INTENT, "watch_status": "TRIGGERED", "terminal_date": CALENDAR[1]}],
                "source_version": "f" * 64, "limits": {"identityUnverifiedBefore": {}},
            })
            atomic_write(files["presentation"], {"rows": []})
            snapshot = {
                "as_of": AS_OF, "source_sha256": "a" * 64, "payload_sha256": "b" * 64,
                "held_symbols": {}, "monitor_state": {"heads": {}, "watches": {}, "pending_references": []},
                "observation_kind": "DRY_RUN_HISTORICAL", "new_live_signals": 0,
                "source_revision_pending": {}, "events": [],
            }
            plain = prepare_bundle(files, self.pipeline, snapshot, CALENDAR, root / "plain")
            result = prepare_bundle(files, self.pipeline, snapshot, CALENDAR, root / "recovered",
                                    settlement_source=self.frame())
            self.assertEqual(result["scheduled_exit_prices"], 1)
            self.assertNotEqual(result["source_version"], plain["source_version"])
            manifest = read(root / "recovered" / "manifest.json")
            self.assertEqual(manifest["quote_fields"], [*FIELDS, "decision_skipped", "scheduled_exit"])
            rows = [row for chunk in manifest["quotes"] for row in read(root / "recovered" / chunk["name"])]
            exact = next(row for row in rows if row[:2] == [SYMBOL, DUE])
            self.assertEqual(exact[2][:-1], [None] * len(FIELDS) + [True])
            self.assertEqual(exact[2][-1], {"open": 95, "factor": 2, "observed_after": AS_OF})
            self.assertTrue(all(not row[2] or row[2][-1] is None or row == exact for row in rows))


if __name__ == "__main__":
    unittest.main()
