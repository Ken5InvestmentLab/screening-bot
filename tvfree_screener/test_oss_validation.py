from __future__ import annotations

import numpy as np
import pandas as pd

from tvfree_screener.oss_validation import purged_kfold_audit, selection_bias_summary


def test_purged_kfold_audit_removes_label_overlap() -> None:
    dates = pd.date_range("2023-01-01", periods=40, freq="D")
    frame = pd.DataFrame(
        {
            "date": dates,
            "exit_date": dates + pd.Timedelta(days=5),
        }
    )
    report = purged_kfold_audit(frame, n_splits=4)

    assert report["audit_clean"].all()
    assert report["final_overlap_fraction"].eq(0.0).all()
    assert report["rows_removed_by_purge"].sum() > 0


def test_selection_bias_summary_reports_raw_and_effective_dsr() -> None:
    returns = np.array(
        [0.010, -0.004, 0.008, 0.002, -0.003, 0.011, 0.005, -0.002, 0.007, 0.001]
        * 4,
        dtype=float,
    )
    trial_sharpes = np.array([0.20, 0.25, 0.31, 0.34, 0.39, 0.43, 0.44, 0.47])

    result = selection_bias_summary(returns, trial_sharpes=trial_sharpes)

    assert 0.0 <= result["psr"] <= 1.0
    selection = result["selection_bias"]
    assert selection is not None
    assert selection["trial_count_raw"] == len(trial_sharpes)
    assert 1 <= selection["trial_count_effective_autocorr"] <= len(trial_sharpes)
    assert 0.0 <= selection["dsr_raw_trial_count"]["dsr"] <= 1.0
    assert 0.0 <= selection["dsr_effective_trial_count"]["dsr"] <= 1.0
