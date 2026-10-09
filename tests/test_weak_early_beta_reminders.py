"""Offline delivery tests: no webhook is ever contacted."""

import contextlib
import io
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd
import requests

from weak_early_beta.cli import command_remind_exits, parser
from weak_early_beta.ledger import LEDGER_COLUMNS, read_ledger, write_ledger
from weak_early_beta.reminders import notify_exit_reminders, save_reminder_receipts


def forward(*symbols):
    rows = []
    for symbol in symbols:
        for selector in ("body_pct_low", "volr20_low"):
            rows.append({
                "detection_id": f"2026-09-30|{symbol}|{selector}",
                "signal_date": pd.Timestamp("2026-09-30"), "symbol": symbol,
                "company_name": "テスト", "selector_id": selector,
                "source_scope": "FORWARD_CAUSAL", "entry_date": pd.Timestamp("2026-10-01"),
                "entry_open": 100, "status": "entered", "price_basis": "TEST_ACTUAL",
                "updated_at": "2026-09-30T17:00:00+09:00",
            })
    return pd.DataFrame(rows).reindex(columns=LEDGER_COLUMNS)


def message(message_id="123"):
    response = Mock()
    response.json.return_value = {"id": message_id, "channel_id": "456"}
    return response


class ReminderDeliveryTests(unittest.TestCase):
    def test_d5_d6_are_independent_and_each_group_is_sent_once(self):
        saved = []
        with patch("weak_early_beta.reminders.requests.post", return_value=message()) as post:
            d5, _ = notify_exit_reminders(forward("4052"), date(2026, 10, 7),
                                         webhook_url="https://example.test/webhook", on_delivery=saved.append)
            self.assertEqual(post.call_count, 1)
            self.assertTrue(d5["exit_reminded_at"].ne("").all())
            self.assertTrue(d5["d6_exit_reminded_at"].eq("").all())
            d6, _ = notify_exit_reminders(d5, date(2026, 10, 8),
                                         webhook_url="https://example.test/webhook", on_delivery=saved.append)
            self.assertEqual(post.call_count, 2)
            self.assertTrue(d6["d6_exit_reminded_at"].ne("").all())
            notify_exit_reminders(d6, date(2026, 10, 8), webhook_url="https://example.test/webhook")
            self.assertEqual(post.call_count, 2)
        self.assertEqual(len(saved), 2)

    def test_success_is_persisted_before_the_next_delivery_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            ledger_path = Path(temporary) / "detections.csv"
            write_ledger(forward("1234", "5678"), ledger_path)
            def delivery(*args, **kwargs):
                if "1234" in kwargs["json"]["embeds"][0]["title"]:
                    return message()
                persisted = read_ledger(ledger_path)
                self.assertTrue(persisted.loc[persisted.symbol.eq("1234"), "exit_reminded_at"].notna().all())
                raise requests.Timeout("secret webhook must not appear")
            with patch("weak_early_beta.reminders.requests.post", side_effect=delivery):
                with self.assertRaisesRegex(RuntimeError, "reconcile") as error:
                    notify_exit_reminders(read_ledger(ledger_path), date(2026, 10, 7),
                                          webhook_url="https://example.test/secret",
                                          on_delivery=lambda frame: save_reminder_receipts(frame, ledger_path))
            self.assertNotIn("secret", str(error.exception))
            persisted = read_ledger(ledger_path)
            self.assertTrue(persisted.loc[persisted.symbol.eq("1234"), "exit_reminded_at"].notna().all())
            self.assertTrue(persisted.loc[persisted.symbol.eq("5678"), "exit_reminded_at"].isna().all())
            self.assertEqual(sorted(p.name for p in Path(temporary).iterdir()), ["detections.csv"])

    def test_atomic_write_failure_keeps_the_previous_receipts(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "detections.csv"
            target.write_bytes(b"previous verified receipts\n")
            with patch("weak_early_beta.reminders.write_ledger", side_effect=OSError("disk failure")):
                with self.assertRaises(OSError):
                    save_reminder_receipts(forward("1234"), target)
            self.assertEqual(target.read_bytes(), b"previous verified receipts\n")
            self.assertEqual(len(list(Path(temporary).iterdir())), 1)

    def test_cli_delivery_only_updates_the_ledger_and_prints_completion(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "detections.csv"
            write_ledger(forward("4052"), target)
            args = parser().parse_args(["remind-exits", "--date", "2026-10-07", "--ledger", str(target)])
            output = io.StringIO()
            with patch.dict("os.environ", {"WEAK_EARLY_BETA_SIGNAL_WEBHOOK_URL": "https://example.test/webhook"}), \
                 patch("weak_early_beta.reminders.requests.post", return_value=message()), \
                 patch("weak_early_beta.cli.write_report") as report, \
                 patch("weak_early_beta.cli.write_fundamental_queue") as queue, contextlib.redirect_stdout(output):
                command_remind_exits(args)
            report.assert_not_called()
            queue.assert_not_called()
            self.assertIn('"reminders": 1', output.getvalue())
            self.assertTrue(read_ledger(target)["exit_reminded_at"].notna().all())
            self.assertEqual(len(list(Path(temporary).iterdir())), 1)

    def test_dry_run_holiday_and_past_dates_never_save_or_send(self):
        with patch("weak_early_beta.reminders.requests.post") as post:
            for target, dry_run in ((date(2026, 10, 7), True), (date(2026, 10, 12), False), (date(2026, 10, 9), False)):
                callback = Mock()
                notify_exit_reminders(forward("4052"), target, dry_run=dry_run, on_delivery=callback)
                callback.assert_not_called()
            post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
