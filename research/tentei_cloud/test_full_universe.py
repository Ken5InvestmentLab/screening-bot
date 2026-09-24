"""Offline contracts for the Cloud universe, Yahoo keys, and coverage report."""
import csv
import datetime as dt
import io
import json
import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook

from coverage_1h import coverage
from daily_data_policy import daily_close_from_payload, detection_gate, settle_due_positions
from fetch_1h import deduplicate_rows, load_symbols, yahoo_symbol
from jpx_universe import discover_excel, extract_universe


def workbook(rows):
    book = Workbook()
    sheet = book.active
    sheet.append(["日付", "コード", "銘柄名", "市場・商品区分"])
    for row in rows:
        sheet.append(["20260831", *row])
    out = io.BytesIO()
    book.save(out)
    return out.getvalue()


class FullUniverseTest(unittest.TestCase):
    def test_jpx_discovery_and_exclusions(self):
        html = '<a href="/other.xlsx">other</a><a href="/markets/x/data_j.xlsx">list</a>'
        self.assertEqual(discover_excel(html), "https://www.jpx.co.jp/markets/x/data_j.xlsx")
        rows, date = extract_universe(workbook([
            ("1234", "A", "プライム（内国株式）"),
            ("2345", "B", "スタンダード（内国株式）"),
            ("345A", "C", "グロース（内国株式）"),
            ("1234", "A", "プライム（内国株式）"),
            ("1305", "ETF", "ETF・ETN"),
            ("8951", "REIT", "REIT・ベンチャーファンド"),
            ("25935", "伊藤園第１種優先株式", "プライム（内国株式）"),
            ("50765", "社債型種類株式", "プライム（内国株式）"),
            ("9999", "foreign", "プライム（外国株式）"),
        ]))
        self.assertEqual(date, "20260831")
        self.assertEqual([r["code"] for r in rows], ["1234", "2345", "345A"])
        self.assertEqual([r["market"] for r in rows], ["Prime", "Standard", "Growth"])

    def test_yahoo_ticker_and_deduplication(self):
        self.assertEqual(yahoo_symbol("345a"), "345A.T")
        self.assertEqual(yahoo_symbol("1234.T"), "1234.T")
        with self.assertRaises(ValueError):
            yahoo_symbol("25935")
        a = ("2026-08-31 09:00:00+0900", "1234", 1, 2, 1, 2, 10)
        b = ("2026-08-31 09:00:00+0900", "1234", 1, 3, 1, 3, 20)
        self.assertEqual(list(deduplicate_rows([a, b]).values()), [b])
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / "symbols.txt"
            p.write_text("1234\n345A\n1234\n", encoding="utf-8")
            self.assertEqual(load_symbols(p, 0, 1), ["1234", "345A"])

    def test_coverage_and_missing_list(self):
        universe = [
            {"code": "1234", "name": "A", "market": "Prime", "ticker": "1234.T"},
            {"code": "345A", "name": "B", "market": "Growth", "ticker": "345A.T"},
        ]
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / "bars.csv"
            with p.open("w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["timestamp", "symbol", "open", "high", "low", "close", "volume"])
                w.writerow(["2026-08-31 09:00:00+0900", "1234", 1, 2, 1, 2, 10])
                w.writerow(["2026-08-31 09:00:00+0900", "1234", 1, 2, 1, 2, 10])
            failures = Path(temp) / "failures.json"
            failures.write_text(json.dumps([{"symbol": "345A", "error": "HTTP 404"}]), encoding="utf-8")
            report, missing = coverage(universe, [p], [failures])
        self.assertEqual(report["target_symbols"], 2)
        self.assertEqual(report["seen_symbols"], 1)
        self.assertEqual(report["coverage_rate"], 0.5)
        self.assertEqual(report["duplicate_rows"], 1)
        self.assertEqual(report["failed_chunks"], 1)
        self.assertEqual(report["failure_topology_chunks"], {"never_seen": 1})
        self.assertEqual([r["code"] for r in missing], ["345A"])

    def test_failed_1h_blocks_detection_but_existing_exit_can_settle(self):
        gate = detection_gate({"1234", "345A"}, {"1234"}, {"345A"})
        self.assertFalse(gate["new_detection_allowed"])
        positions = [{"signal_id": "existing", "symbol": "1234", "exit_date": "2026-08-31",
                      "entry_price": "100"}]
        rows = settle_due_positions(positions, dt.date(2026, 8, 31), lambda code, day: 110.0)
        self.assertEqual(rows[0]["status"], "settled")
        self.assertAlmostEqual(rows[0]["return_5bd"], 0.1)
        payload = {"chart": {"result": [{"timestamp": [int(dt.datetime(2026, 8, 31, tzinfo=dt.timezone.utc).timestamp())],
                                           "indicators": {"quote": [{"close": [110]}]}}]}}
        self.assertEqual(daily_close_from_payload("1234", dt.date(2026, 8, 31), payload), 110.0)
        with self.assertRaises(ValueError):
            daily_close_from_payload("1234", dt.date(2026, 9, 1), payload)


if __name__ == "__main__":
    unittest.main()
