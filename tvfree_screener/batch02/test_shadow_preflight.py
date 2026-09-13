import unittest

from tvfree_screener.batch02.shadow_preflight import (
    expected_bin_cutoff,
    validate_shadow_export_row,
    validate_shadow_export_rows,
)


BASE = {
    "experiment_id": "E",
    "model_freeze_id": "F",
    "symbol": "1234",
    "signal_date": "2026-09-14",
    "bin_name": "AM_09_13",
    "feature_cutoff": "2026-09-14T13:00:00+09:00",
    "source_tag": "RAW_CAUSAL_INTRADAY",
    "rank": 1,
}


class ShadowPreflightTests(unittest.TestCase):
    def test_valid_am_row_passes(self):
        validate_shadow_export_row(BASE)

    def test_postclose_tag_rejected(self):
        row = dict(BASE, source_tag="POSTCLOSE_RECON_ONLY")
        with self.assertRaises(ValueError):
            validate_shadow_export_row(row)

    def test_wrong_day_cutoff_rejected(self):
        row = dict(BASE, feature_cutoff="2026-09-15T13:00:00+09:00")
        with self.assertRaises(ValueError):
            validate_shadow_export_row(row)

    def test_wrong_am_cutoff_rejected(self):
        row = dict(BASE, feature_cutoff="2026-09-14T15:30:00+09:00")
        with self.assertRaises(ValueError):
            validate_shadow_export_row(row)

    def test_pm_close_change_is_enforced(self):
        pre = dict(
            BASE,
            signal_date="2024-11-01",
            bin_name="PM_13_CLOSE",
            feature_cutoff="2024-11-01T15:00:00+09:00",
        )
        post = dict(
            BASE,
            signal_date="2024-11-05",
            bin_name="PM_13_CLOSE",
            feature_cutoff="2024-11-05T15:30:00+09:00",
        )
        validate_shadow_export_row(pre)
        validate_shadow_export_row(post)
        wrong = dict(post, feature_cutoff="2024-11-05T15:00:00+09:00")
        with self.assertRaises(ValueError):
            validate_shadow_export_row(wrong)

    def test_duplicate_key_rejected(self):
        with self.assertRaises(ValueError):
            validate_shadow_export_rows([BASE, dict(BASE)])

    def test_rank_must_be_positive(self):
        with self.assertRaises(ValueError):
            validate_shadow_export_row(dict(BASE, rank=0))

    def test_timezone_is_normalized_to_jst(self):
        row = dict(BASE, feature_cutoff="2026-09-14T04:00:00+00:00")
        validate_shadow_export_row(row)


if __name__ == "__main__":
    unittest.main()
