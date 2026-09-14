import pandas as pd
import pytest

from tvfree_screener.edinet_oss_sample_selector import select_real_sample


def _metadata() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"doc_id": "B", "doc_type_code": "120", "submit_datetime": "2023-01-05T09:00:00+09:00"},
            {"doc_id": "A", "doc_type_code": "120", "submit_datetime": "2023-01-05T09:00:00+09:00"},
            {"doc_id": "C", "doc_type_code": "120", "submit_datetime": "2023-02-01T09:00:00+09:00"},
            {"doc_id": "D", "doc_type_code": "130", "submit_datetime": "2023-01-02T09:00:00+09:00"},
            {"doc_id": "E", "doc_type_code": "130", "submit_datetime": "2023-01-03T09:00:00+09:00"},
            {"doc_id": "F", "doc_type_code": "130", "submit_datetime": "2023-01-04T09:00:00+09:00"},
            {"doc_id": "G", "doc_type_code": "120", "submit_datetime": "2023-04-03T09:00:00+09:00"},
            {"doc_id": "H", "doc_type_code": "120", "submit_datetime": "2023-04-04T09:00:00+09:00"},
            {"doc_id": "IGNORED", "doc_type_code": "140", "submit_datetime": "2023-01-01T09:00:00+09:00"},
            # Exact doc_id duplicate must not create a replacement slot.
            {"doc_id": "A", "doc_type_code": "120", "submit_datetime": "2023-01-06T09:00:00+09:00"},
        ]
    )


def test_selector_is_deterministic_by_quarter_doc_type_then_submit_and_doc_id():
    selected, receipt = select_real_sample(
        _metadata(),
        source_coverage_start="2023-01-01T00:00:00+09:00",
        source_coverage_end="2025-12-31T23:59:59+09:00",
    )

    # Q1/120 tie resolves by doc_id A before B; only two are selected.
    assert selected.loc[
        (selected["calendar_quarter"] == "2023Q1")
        & (selected["doc_type_code"] == "120"),
        "doc_id",
    ].tolist() == ["A", "B"]
    assert selected.loc[
        (selected["calendar_quarter"] == "2023Q1")
        & (selected["doc_type_code"] == "130"),
        "doc_id",
    ].tolist() == ["D", "E"]
    assert selected.loc[
        (selected["calendar_quarter"] == "2023Q2")
        & (selected["doc_type_code"] == "120"),
        "doc_id",
    ].tolist() == ["G", "H"]
    assert "IGNORED" not in receipt["selected_doc_ids"]
    assert receipt["strategy_outcomes_opened"] is False
    assert receipt["no_replacement_rule"] is True


def test_selector_fails_closed_if_source_coverage_is_incomplete():
    with pytest.raises(ValueError, match="does not cover the full preregistered"):
        select_real_sample(
            _metadata(),
            source_coverage_start="2023-01-02T00:00:00+09:00",
            source_coverage_end="2025-12-31T23:59:59+09:00",
        )

    with pytest.raises(ValueError, match="does not cover the full preregistered"):
        select_real_sample(
            _metadata(),
            source_coverage_start="2023-01-01T00:00:00+09:00",
            source_coverage_end="2025-12-30T23:59:59+09:00",
        )


def test_selector_rejects_missing_or_blank_required_metadata():
    with pytest.raises(ValueError, match="missing metadata columns"):
        select_real_sample(
            _metadata().drop(columns=["doc_type_code"]),
            source_coverage_start="2023-01-01T00:00:00+09:00",
            source_coverage_end="2025-12-31T23:59:59+09:00",
        )

    bad = _metadata()
    bad.loc[0, "doc_id"] = ""
    with pytest.raises(ValueError, match="blank doc_id"):
        select_real_sample(
            bad,
            source_coverage_start="2023-01-01T00:00:00+09:00",
            source_coverage_end="2025-12-31T23:59:59+09:00",
        )
