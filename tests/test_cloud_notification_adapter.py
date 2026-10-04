"""Local-only candidate/calendar and durable-schema contract tests."""
import importlib.util
import json
from pathlib import Path
import re
import sqlite3
import unittest
from unittest.mock import patch

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("cloud_notification_adapter",
    ROOT / "weak-early-beta-gate/scripts/build-notification-events.py")
ADAPTER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ADAPTER)


class CloudNotificationAdapterTests(unittest.TestCase):
    def row(self, **changes):
        return {"detection_id": "2026-12-28|9999|silence", "signal_date": "2026-12-28",
                "symbol": "9999", "source_scope": "FORWARD_CAUSAL", **changes}

    def test_year_boundary_and_bank_holidays_come_from_shared_calendar(self):
        events = ADAPTER.build_events(pd.DataFrame([self.row()]), "a" * 64,
            pd.Timestamp("2027-01-07T08:00:00+09:00"))
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["kind"], "reminder")
        self.assertEqual(events[0]["endpoints"]["d5_close"]["date"], "2027-01-06")
        self.assertEqual(events[0]["endpoints"]["d6_open"]["date"], "2027-01-07")
        self.assertIsNone(events[0]["endpoints"]["d6_open"]["actual_price"])

    def test_conflicting_ledger_endpoint_date_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "endpoint date mismatch"):
            ADAPTER.build_events(pd.DataFrame([self.row(sixth_xtks_exit_date="2027-01-08")]),
                "a" * 64, pd.Timestamp("2027-01-08T10:00:00+09:00"))

    def test_reconstructions_and_2022_never_become_new_notifications(self):
        for row in [self.row(source_scope="EXACT_CANONICAL_2023_2026"), self.row(signal_date="2022-12-28")]:
            self.assertEqual(ADAPTER.build_events(pd.DataFrame([row]), "a" * 64,
                pd.Timestamp("2026-12-28T17:00:00+09:00")), [])

    def test_missing_d5_acquisition_is_not_synthesized_from_updated_at(self):
        event = ADAPTER.build_events(pd.DataFrame([self.row(updated_at="2027-01-07T17:00:00+09:00")]),
            "a" * 64, pd.Timestamp("2027-01-07T17:00:00+09:00"))[0]
        self.assertEqual(event["endpoints"]["d5_close"]["status"], "missing")
        self.assertIsNone(event["endpoints"]["d5_close"]["fetched_at"])

    def test_naive_time_or_missing_ledger_digest_rejected(self):
        for digest, as_of in [("a" * 64, pd.Timestamp("2026-12-28")), ("", pd.Timestamp("2026-12-28T17:00:00+09:00"))]:
            with self.assertRaises(ValueError):
                ADAPTER.build_events(pd.DataFrame(), digest, as_of)

    def test_weekends_and_bank_holidays_generate_no_candidates(self):
        for day in ("2026-10-04", "2026-10-12", "2027-01-01", "2027-01-02", "2027-01-03"):
            self.assertEqual(ADAPTER.build_events(pd.DataFrame([self.row(signal_date=day)]), "a" * 64,
                pd.Timestamp(day + "T08:00:00+09:00")), [])

    def test_private_sql_plan_imports_exact_json_idempotently_and_preserves_receipts(self):
        now = pd.Timestamp("2026-12-28T17:00:00+09:00")
        events = ADAPTER.build_events(pd.DataFrame([self.row(symbol="9999'quoted")]), "a" * 64, now)
        db = sqlite3.connect(":memory:")
        for path in sorted((ROOT / "weak-early-beta-gate/migrations").glob("*.sql")):
            db.executescript(path.read_text(encoding="utf-8"))
        db.execute("INSERT INTO cloud_member_preferences VALUES ('memberA','{}','unchanged')")
        db.execute("INSERT INTO cloud_push_dispatch_receipts VALUES ('memberA','device','event','unknown','no_auto_retry','unchanged')")
        db.commit()
        plan = ADAPTER.build_sql_plan(events, "a" * 64, now)
        db.executescript(plan)
        db.executescript(plan)
        row = db.execute("SELECT event_json,available_at FROM cloud_notification_events").fetchone()
        self.assertEqual(json.loads(row[0]), events[0])
        self.assertEqual(row[1], "2026-12-28T08:00:00.000Z")
        self.assertEqual(db.execute("SELECT count(*) FROM cloud_notification_events").fetchone()[0], 1)
        revised = {**events[0], "source_ledger_revision": "b" * 64}
        db.executescript(ADAPTER.build_sql_plan([revised], "b" * 64, now + pd.Timedelta(minutes=1)))
        self.assertEqual(db.execute("SELECT count(*) FROM cloud_notification_events").fetchone()[0], 1)
        self.assertEqual(db.execute("SELECT source_ledger_revision FROM cloud_notification_events").fetchone()[0], "b" * 64)
        self.assertEqual(db.execute("SELECT preferences_json,updated_at FROM cloud_member_preferences").fetchone(), ("{}", "unchanged"))
        self.assertEqual(db.execute("SELECT status,reason FROM cloud_push_dispatch_receipts").fetchone(), ("unknown", "no_auto_retry"))
        self.assertNotIn("DELETE", plan)
        with self.assertRaises(ValueError):
            ADAPTER.build_sql_plan([events[0], events[0]], "a" * 64, now)
        with self.assertRaises(ValueError):
            ADAPTER.build_sql_plan([{**events[0], "kind": "result"}], "a" * 64, now)
        db.close()

    def test_overlapping_selectors_emit_one_stock_notification(self):
        rows = [self.row(), self.row(detection_id="2026-12-28|9999|dive")]
        events = ADAPTER.build_events(pd.DataFrame(rows), "a" * 64, pd.Timestamp("2026-12-28T17:00:00+09:00"))
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["signal_id"], "2026-12-28|9999")

    def test_conflicting_verified_overlap_is_rejected(self):
        rows = [self.row(signal_actual_close=900, signal_actual_close_observed_at="2026-12-28T16:00:00+09:00"),
                self.row(detection_id="2026-12-28|9999|dive", signal_actual_close=901,
                         signal_actual_close_observed_at="2026-12-28T16:00:00+09:00")]
        # The ledger verifier has its own receipt tests; here exercise aggregation
        # after two observations have passed that boundary independently.
        with patch.object(ADAPTER, "signal_actual_close_verified", return_value=True):
            with self.assertRaisesRegex(ValueError, "conflicting overlapping"):
                ADAPTER.build_events(pd.DataFrame(rows), "a" * 64, pd.Timestamp("2026-12-28T17:00:00+09:00"))

    def test_d1_schema_is_idempotent_and_receipts_deduplicate(self):
        db = sqlite3.connect(":memory:")
        schema = (ROOT / "weak-early-beta-gate/migrations/0001_cloud_preferences.sql").read_text(encoding="utf-8")
        db.executescript(schema)
        db.executescript(schema)
        db.execute("INSERT INTO cloud_member_preferences VALUES (?, ?, ?)", ("memberA", '{}', "2026-10-04"))
        self.assertEqual(db.execute("SELECT preferences_json FROM cloud_member_preferences WHERE member_id = ?", ("memberA",)).fetchone()[0], "{}")
        values = ("memberA", "event1", "dry_run_eligible", "verified", "now", "now", 1)
        db.execute("INSERT INTO cloud_notification_deliveries VALUES (?, ?, ?, ?, ?, ?, ?)", values)
        with self.assertRaises(sqlite3.IntegrityError):
            db.execute("INSERT INTO cloud_notification_deliveries VALUES (?, ?, ?, ?, ?, ?, ?)", values)
        with self.assertRaises(sqlite3.IntegrityError):
            db.execute("INSERT INTO cloud_member_preferences VALUES (?, ?, ?)", ("memberB", '{broken', "now"))
        db.close()

    def scan_database(self):
        db = sqlite3.connect(":memory:")
        db.row_factory = sqlite3.Row
        for _ in range(2):
            for path in sorted((ROOT / "weak-early-beta-gate/migrations").glob("*.sql")):
                db.executescript(path.read_text(encoding="utf-8"))
        for index in range(205):
            db.execute("INSERT INTO cloud_notification_events VALUES (?, ?, ?, ?)",
                (f"private-{index:03}", json.dumps({"signal_id": f"private-signal-{index:03}"}),
                 "2026-10-01T00:00:00.000Z", "a" * 64))
        return db

    def scan_statement(self, prefix, source_file="cloud-api.ts"):
        # Execute the production statements against real SQLite, rather than a
        # second hand-written pagination query that could conceal SQL mistakes.
        source = (ROOT / "weak-early-beta-gate/src" / source_file).read_text(encoding="utf-8")
        match = re.search(r"`(" + re.escape(prefix) + r"[^`]+)`", source)
        self.assertIsNotNone(match, prefix)
        return match.group(1)

    def test_real_sql_scan_reaches_205_and_revisits_held_after_wrap(self):
        db = self.scan_database()
        initialize = self.scan_statement("INSERT OR IGNORE INTO cloud_notification_scan_progress")
        select_progress = self.scan_statement("SELECT after_available_at")
        select_page = self.scan_statement("SELECT source_event_key")
        advance = self.scan_statement("UPDATE cloud_notification_scan_progress")
        delivery = self.scan_statement("INSERT INTO cloud_notification_deliveries")
        now = "2026-10-02T00:00:00.000Z"
        db.execute(initialize, ("member-a", now))
        for state in ("held", "dry_run_eligible"):
            visited = []
            page_count = 0
            while True:
                progress = db.execute(select_progress, ("member-a",)).fetchone()
                cutoff = progress["cycle_cutoff_at"] or now
                rows = db.execute(select_page, (cutoff, progress["after_available_at"],
                    progress["after_source_event_key"])).fetchall()
                self.assertLessEqual(len(rows), 21)
                page = rows[:20]
                has_more = len(rows) > 20
                visited.extend(row["source_event_key"] for row in page)
                for row in page:
                    db.execute(delivery, ("member-a", row["source_event_key"], state, "dry-run", now, now))
                last = page[-1] if page else None
                changed = db.execute(advance, (last["available_at"] if has_more else "",
                    last["source_event_key"] if has_more else "", cutoff if has_more else "", now,
                    "member-a", progress["version"])).rowcount
                self.assertEqual(changed, 1)
                page_count += 1
                self.assertLessEqual(page_count, 11)
                if not has_more:
                    break
            self.assertEqual(visited, [f"private-{index:03}" for index in range(205)])
            self.assertEqual(page_count, 11)
        self.assertEqual(db.execute("SELECT count(*) FROM cloud_notification_deliveries WHERE status='dry_run_eligible' AND attempts=2").fetchone()[0], 205)
        self.assertEqual(db.execute("SELECT count(*) FROM cloud_notification_deliveries WHERE status='sent'").fetchone()[0], 0)
        plan = db.execute("EXPLAIN QUERY PLAN " + select_page, (now, "", "")).fetchall()
        self.assertTrue(any("cloud_notification_events_scan" in row[3] for row in plan))
        self.assertTrue(any("(available_at,source_event_key)>(?,?)" in row[3] for row in plan))
        db.close()

    def test_personal_runner_sql_pages_205_separately_and_rejects_late_cursor(self):
        db = self.scan_database()
        query = lambda prefix: self.scan_statement(prefix, "cloud-push-runner.ts")
        initialize, progress_query, page_query, advance = [query(prefix) for prefix in
            ("INSERT OR IGNORE INTO cloud_notification_scan_progress", "SELECT after_available_at",
             "SELECT source_event_key", "UPDATE cloud_notification_scan_progress")]
        now, cursor = "2026-10-02T00:00:00.000Z", "personal-push:member-a:device-a"
        for member in (cursor, "member-a", "personal-push:member-a:device-b"):
            db.execute(initialize, (member, now))
        for _ in range(2):
            visited = []
            while True:
                progress = db.execute(progress_query, (cursor,)).fetchone()
                cutoff = progress["cycle_cutoff_at"] or now
                rows = db.execute(page_query, (cutoff, progress["after_available_at"], progress["after_source_event_key"])).fetchall()
                page, more = rows[:20], len(rows) > 20
                visited.extend(row["source_event_key"] for row in page)
                values = (page[-1]["available_at"] if more else "", page[-1]["source_event_key"] if more else "",
                    cutoff if more else "", now, cursor, progress["version"])
                self.assertEqual(db.execute(advance, values).rowcount, 1)
                self.assertEqual(db.execute(advance, values).rowcount, 0)
                if not more:
                    break
            self.assertEqual(visited, [f"private-{index:03}" for index in range(205)])
        for member in ("member-a", "personal-push:member-a:device-b"):
            self.assertEqual(db.execute(progress_query, (member,)).fetchone()["version"], 0)
        self.assertEqual(db.execute("SELECT count(*) FROM cloud_push_dispatch_receipts").fetchone()[0], 0)
        db.close()

    def test_real_sql_cursor_compare_and_swap_prevents_late_regression(self):
        db = self.scan_database()
        initialize = self.scan_statement("INSERT OR IGNORE INTO cloud_notification_scan_progress")
        select_progress = self.scan_statement("SELECT after_available_at")
        advance = self.scan_statement("UPDATE cloud_notification_scan_progress")
        now = "2026-10-02T00:00:00.000Z"
        for member in ("member-a", "member-b"):
            db.execute(initialize, (member, now))
        first = db.execute(select_progress, ("member-a",)).fetchone()
        late = db.execute(select_progress, ("member-a",)).fetchone()
        values = ("2026-10-01T00:00:00.000Z", "private-019", now, now, "member-a", first["version"])
        self.assertEqual(db.execute(advance, values).rowcount, 1)
        current = db.execute(select_progress, ("member-a",)).fetchone()
        self.assertEqual(db.execute(advance, (values[0], "private-039", now, now, "member-a", current["version"])).rowcount, 1)
        self.assertEqual(db.execute(advance, ("", "", "", now, "member-a", late["version"])).rowcount, 0)
        self.assertEqual(db.execute(select_progress, ("member-a",)).fetchone()["after_source_event_key"], "private-039")
        self.assertEqual(db.execute(select_progress, ("member-b",)).fetchone()["version"], 0)
        db.close()


if __name__ == "__main__":
    unittest.main()
