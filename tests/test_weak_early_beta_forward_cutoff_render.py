import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from weak_early_beta import report


class ForwardCutoffRenderTests(unittest.TestCase):
    def test_saved_forward_analysis_cutoff_is_displayed_in_japan_time_separately_from_detection(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state_path = root / "weak_early_beta/fundamental_worker/state/premium_alert_state.json"
            state_path.parent.mkdir(parents=True)
            identity = "weak-early-beta:2026-10-05:336A"
            cutoff = "2026-10-06T00:00:00.123Z"
            saved_report = {"alertId": identity, "auditStatus": "pass", "signalDate": "2026-10-05",
                            "symbolCode": "336A", "analysisCutoff": cutoff, "disclosures": [
                                {"url": "https://example.com/date.pdf", "title": "日付のみ", "publishedAt": "2026-10-05T00:00:00+09:00", "publishedAtPrecision": "date_only", "contentReviewed": True},
                                {"url": "https://example.com/utc.pdf", "title": "UTC時刻", "publishedAt": "2026-10-05T08:00:00Z", "contentReviewed": True},
                            ]}
            state_path.write_text(json.dumps({"completed": {identity: {"delivery": "html", "analysisBasis": "analysis_start",
                "analysisCutoff": cutoff, "report": saved_report}}}), encoding="utf-8")
            report._historical_snapshot_metadata.cache_clear()
            try:
                with patch.object(report, "ROOT", root):
                    metadata = report._historical_snapshot_metadata()[("2026-10-05", "336A")]
                    rendered = report._fundamental_html("材料インパクト\n様子見：確認済み。", "社名", "336A", "2026-10-05", metadata)
                self.assertIn("検出日: 2026-10-05", rendered)
                self.assertIn("分析基準日時: 2026-10-06T09:00:00.123000+09:00 (日本時間)", rendered)
                self.assertNotIn("16:15", rendered)
                self.assertEqual(metadata["disclosures"]["https://example.com/date.pdf"], "2026-10-05 日付のみ(時刻未確認)")
                self.assertEqual(metadata["disclosures"]["https://example.com/utc.pdf"], "2026-10-05 UTC時刻(17:00)")
            finally:
                report._historical_snapshot_metadata.cache_clear()

    def test_unmatched_saved_cutoff_is_not_used_as_verified_metadata(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state_path = root / "weak_early_beta/fundamental_worker/state/premium_alert_state.json"
            state_path.parent.mkdir(parents=True)
            identity = "weak-early-beta:2026-10-05:336A"
            state_path.write_text(json.dumps({"completed": {identity: {"delivery": "html", "analysisBasis": "analysis_start",
                "analysisCutoff": "2026-10-05T09:00:00.000Z", "report": {"alertId": identity,
                "auditStatus": "pass", "signalDate": "2026-10-05", "symbolCode": "336A",
                "analysisCutoff": "2026-10-05T09:00:00.001Z"}}}}), encoding="utf-8")
            report._historical_snapshot_metadata.cache_clear()
            try:
                with patch.object(report, "ROOT", root):
                    self.assertEqual(report._historical_snapshot_metadata(), {})
            finally:
                report._historical_snapshot_metadata.cache_clear()


if __name__ == "__main__":
    unittest.main()
