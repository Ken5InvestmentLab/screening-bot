"""Missing daily prices are final for detection and remain absent from its features."""

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from weak_early_beta.new_a import monitor
from weak_early_beta.new_a.packet import prepare_packet
from weak_early_beta.new_a.pipeline import Pipeline


SYMBOL = "1111"
OTHER = "2222"


def bar(*, candidate=False, close=104.0, source_usable=True):
    return {
        "open": 102.0, "high": 108.0, "low": 100.0, "close": close,
        "volume": 400000.0, "actual_close": close, "actual_volume": 400000.0,
        "split_factor": 1.0, "source_usable": source_usable,
        "candidate": candidate, "low20": 100.0, "high20": 110.0,
        "median_turnover20": 40000000.0,
    }


class MissingQuoteDecisions(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.db_path = Path(temp.name) / "state.sqlite"
        self.calendar = pd.bdate_range("2025-04-01", periods=74).strftime("%Y-%m-%d").tolist()
        self.anchor_index = 68
        self.anchor, self.missing, self.next_day, self.following_day = self.calendar[68:72]
        self.seed = monitor.initial(self.calendar, [SYMBOL, OTHER], "MISSING_QUOTE_TEST")
        self.seed["cursor"] = self.anchor_index
        self.seed["previous"] = {symbol: bar() for symbol in self.seed["symbols"]}

    def pipeline(self):
        pipeline = Pipeline(self.db_path, self.seed)
        self.addCleanup(pipeline.close)
        return pipeline

    def run_day(self, pipeline, day, symbol_rows, *, revision="a", **updates):
        rows = {
            date: {SYMBOL: row, OTHER: bar()}
            for date, row in symbol_rows.items()
        }
        args = {
            "as_of": day, "observed_at": day + "T08:00:00Z",
            "calendar": self.calendar, "rows_by_day": rows,
            "source_hash": revision * 64, "quality_verified": True,
            "universe": self.seed["symbols"], "freeze_missing_quotes": True,
        }
        args.update(updates)
        return pipeline.run(**args)

    def seed_watch(self, start_index):
        episode = {
            "symbol": SYMBOL, "candidate_date": self.calendar[start_index],
            "episode_id": 1, "support": 100.0, "resistance": 110.0,
            "priority_score": 40000000.0, "detection_count": 1,
        }
        self.seed["active"][SYMBOL] = episode.copy()
        self.seed["sequence"][SYMBOL] = 1
        self.seed["watches"][SYMBOL + "|1"] = {"episode": episode.copy(), "start_index": start_index}
        return episode

    def test_skip_is_durable_and_same_day_revision_cannot_emit(self):
        pipeline = self.pipeline()
        rows = {self.anchor: bar(), self.missing: None}
        first = self.run_day(pipeline, self.missing, rows)
        self.assertEqual(first["processed_symbol_sessions"], 1)
        self.assertEqual(first["held"][SYMBOL], {"day": self.missing, "reason": "MISSING_SOURCE"})
        self.assertEqual(first["events"], [])
        self.assertEqual(pipeline.read(SYMBOL)["cursor"], self.anchor_index + 1)
        self.assertNotIn((SYMBOL, self.missing), pipeline.observed_quotes())

        reopened = self.pipeline()
        self.assertEqual(reopened.missing_quote_days(), {(SYMBOL, self.missing)})
        rows[self.missing] = bar(candidate=True)
        replay = self.run_day(
            reopened, self.missing, rows, revision="b",
            resume_held=True, predecessor_source_hash="a" * 64,
        )
        self.assertEqual(replay["events"], [])
        self.assertEqual(replay["held"], first["held"])
        self.assertEqual(reopened.all_events(), [])
        self.assertNotIn((SYMBOL, self.missing), reopened.observed_quotes())

    def test_legacy_missing_hold_migrates_without_replay(self):
        pipeline = self.pipeline()
        first = self.run_day(
            pipeline, self.missing, {self.anchor: bar(), self.missing: None},
            freeze_missing_quotes=False,
        )
        self.assertEqual(first["held"][SYMBOL]["reason"], "MISSING_SOURCE")
        self.assertEqual(pipeline.read(SYMBOL)["cursor"], self.anchor_index)
        self.assertEqual(pipeline.missing_quote_days(), {(SYMBOL, self.missing)})

        later = self.run_day(
            pipeline, self.next_day,
            {self.anchor: bar(), self.missing: bar(candidate=True), self.next_day: bar()},
            revision="b",
        )
        self.assertFalse(later["held"])
        self.assertFalse(later["events"])
        self.assertEqual(pipeline.missing_quote_days(), {(SYMBOL, self.missing)})
        self.assertIn((SYMBOL, self.next_day), pipeline.observed_quotes())
        self.assertNotIn((SYMBOL, self.missing), pipeline.observed_quotes())

    def test_next_valid_bar_rebases_without_using_pre_gap_close_as_yesterday(self):
        self.seed_watch(self.anchor_index - 2)
        pipeline = self.pipeline()
        self.run_day(pipeline, self.missing, {self.anchor: bar(), self.missing: None})
        rebased_anchor = dict(bar(), open=51.0, high=54.0, low=50.0, close=52.0, split_factor=2.0)
        rebased_today = dict(bar(close=107.0), open=51.0, high=54.0, low=50.0, close=53.5, split_factor=2.0)
        later = self.run_day(
            pipeline, self.next_day,
            {self.anchor: rebased_anchor, self.missing: bar(candidate=True), self.next_day: rebased_today},
            revision="b",
        )
        self.assertEqual(later["events"], [])
        self.assertEqual(pipeline.observed_quotes()[(SYMBOL, self.next_day)]["close"], 107.0)
        self.assertIn(SYMBOL + "|1", pipeline.export_current()["watches"])
        rebased_following = dict(rebased_today, close=54.0, actual_close=108.0)
        next_active = self.run_day(
            pipeline, self.following_day, {self.next_day: rebased_today, self.following_day: rebased_following},
            revision="c",
        )
        self.assertEqual([event["kind"] for event in next_active["events"]], ["ENTRY_CANDIDATE", "WATCH_TERMINAL"])
        self.assertEqual(next_active["events"][0]["session"], self.following_day)

    def test_revised_last_observed_actual_close_remains_held(self):
        pipeline = self.pipeline()
        self.run_day(pipeline, self.missing, {self.anchor: bar(), self.missing: None})
        later = self.run_day(
            pipeline, self.next_day,
            {self.anchor: bar(close=105.0), self.missing: bar(), self.next_day: bar(candidate=True)},
            revision="b",
        )
        self.assertEqual(later["held"][SYMBOL]["reason"], "PRIOR_OBSERVED_CLOSE_REVISED")
        self.assertEqual(pipeline.read(SYMBOL)["cursor"], self.anchor_index + 1)
        self.assertNotIn((SYMBOL, self.next_day), pipeline.observed_quotes())

    def test_skipped_deadline_expires_on_next_valid_day_and_entry_remains_unresolved(self):
        episode = self.seed_watch(self.anchor_index - 19)
        self.seed["pending"] = [{
            **episode, "episode_id": 2, "entry_index": self.anchor_index + 1,
            "reference_exit_index": self.anchor_index + 20,
            "reference_entry_date": self.missing, "reference_exit_date": None,
            "price_status": "UNCONFIRMED_NEXT_OPEN", "execution_status": "NOT_EXECUTED",
        }]
        pipeline = self.pipeline()
        first = self.run_day(pipeline, self.missing, {self.anchor: bar(), self.missing: None})
        self.assertEqual(first["events"], [])
        state = pipeline.export_current()
        self.assertEqual(state["pending_references"][0]["price_status"], "UNRESOLVED_OPEN")
        self.assertNotIn("reference_open", state["pending_references"][0])
        later = self.run_day(
            pipeline, self.next_day,
            {self.anchor: bar(), self.missing: bar(close=107.0), self.next_day: bar(close=108.0)},
            revision="b",
        )
        self.assertEqual(len(later["events"]), 1)
        event = later["events"][0]
        self.assertEqual((event["kind"], event["reason"]), ("WATCH_TERMINAL", "EXPIRED"))
        self.assertEqual((event["session"], event["expired_on"]), (self.next_day, self.missing))
        self.assertFalse(pipeline.export_current()["watches"])

    def test_restriction_and_quarantine_do_not_become_missing_day_decisions(self):
        pipeline = self.pipeline()
        restrictions = {SYMBOL: [{"start": self.missing, "reason": "VERIFIED_RESTRICTED"}]}
        result = self.run_day(
            pipeline, self.missing, {}, restrictions=restrictions,
            rows_by_day={
                self.anchor: {SYMBOL: bar(), OTHER: bar()},
                self.missing: {SYMBOL: None, OTHER: bar(source_usable=False)},
            },
        )
        self.assertEqual(result["held"][SYMBOL]["reason"], "VERIFIED_RESTRICTED")
        self.assertEqual(result["held"][OTHER]["reason"], "SOURCE_QUARANTINED")
        self.assertEqual(pipeline.missing_quote_days(), set())
        self.assertTrue(all(pipeline.read(sym)["cursor"] == self.anchor_index for sym in self.seed["symbols"]))

    def test_packet_reindexes_late_quote_as_missing_before_rolling_features(self):
        raw_rows = [
            {"date": day, "symbol": symbol, **bar()}
            for day in self.calendar[:71] for symbol in self.seed["symbols"]
        ]
        source = {"frame": pd.DataFrame(raw_rows), "source_hash": "a" * 64, "restrictions": []}
        heads = {SYMBOL: self.missing, OTHER: self.missing}
        options = {"as_of": self.next_day, "observed_at": self.next_day + "T08:00:00Z", "dry_run": True}
        unfiltered = prepare_packet(source, self.seed, self.calendar, heads, **options)
        filtered = prepare_packet(
            source, self.seed, self.calendar, heads,
            missing_quote_days={(SYMBOL, self.missing)}, **options,
        )
        rows = filtered["rows_by_day"]
        self.assertIn(self.anchor, rows)
        self.assertIsNotNone(rows[self.anchor][SYMBOL])
        self.assertIsNone(rows[self.missing][SYMBOL])
        self.assertIsNone(rows[self.next_day][SYMBOL]["low20"])
        self.assertEqual(unfiltered["rows_by_day"][self.next_day][SYMBOL]["low20"], 100.0)
        self.assertEqual(rows[self.next_day][OTHER], unfiltered["rows_by_day"][self.next_day][OTHER])
