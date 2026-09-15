import json

import pytest

from tvfree_screener.edinet_metadata_snapshot import freeze_metadata_snapshot


def _write_day(root, day, rows, *, status="200"):
    (root / f"{day}.json").write_text(
        json.dumps(
            {
                "metadata": {"status": status},
                "results": rows,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_snapshot_freezes_complete_daily_coverage_and_is_outcome_blind(tmp_path):
    _write_day(
        tmp_path,
        "2023-01-01",
        [
            {
                "docID": "S1001",
                "docTypeCode": "120",
                "submitDateTime": "2023-01-01 09:10",
            }
        ],
    )
    _write_day(
        tmp_path,
        "2023-01-02",
        [
            {
                "docID": "S1002",
                "docTypeCode": "130",
                "submitDateTime": "2023-01-02T10:20:00+09:00",
            }
        ],
    )

    frame, manifest = freeze_metadata_snapshot(
        tmp_path,
        start="2023-01-01",
        end="2023-01-02",
    )

    assert frame["doc_id"].tolist() == ["S1001", "S1002"]
    assert frame["submit_datetime"].tolist() == [
        "2023-01-01T09:10:00+09:00",
        "2023-01-02T10:20:00+09:00",
    ]
    assert manifest["coverage"] == {
        "start": "2023-01-01",
        "end": "2023-01-02",
        "expected_calendar_days": 2,
        "observed_calendar_days": 2,
        "full_period_pass": True,
    }
    assert manifest["strategy_outcomes_opened"] is False
    assert manifest["parser_outputs_used_for_selection"] is False
    assert len(manifest["raw_daily_files"]) == 2
    assert len(manifest["raw_daily_hash_chain_sha256"]) == 64


def test_snapshot_fails_closed_on_missing_calendar_day(tmp_path):
    _write_day(tmp_path, "2023-01-01", [])

    with pytest.raises(ValueError, match="incomplete EDINET metadata date coverage"):
        freeze_metadata_snapshot(
            tmp_path,
            start="2023-01-01",
            end="2023-01-02",
        )


def test_snapshot_fails_closed_on_non_success_status_and_malformed_row(tmp_path):
    _write_day(tmp_path, "2023-01-01", [], status="500")
    with pytest.raises(ValueError, match="status is not 200"):
        freeze_metadata_snapshot(tmp_path, start="2023-01-01", end="2023-01-01")

    _write_day(
        tmp_path,
        "2023-01-01",
        [{"docID": "S1001", "docTypeCode": "120"}],
    )
    with pytest.raises(ValueError, match="missing docID/docTypeCode/submitDateTime"):
        freeze_metadata_snapshot(tmp_path, start="2023-01-01", end="2023-01-01")


def test_snapshot_retains_sample_safe_duplicate_doc_observations_and_records_receipt(tmp_path):
    row = {
        "docID": "SAME",
        "docTypeCode": "120",
        "submitDateTime": "2023-01-01 09:00",
    }
    _write_day(tmp_path, "2023-01-01", [row])
    _write_day(tmp_path, "2023-01-02", [row])

    frame, manifest = freeze_metadata_snapshot(
        tmp_path,
        start="2023-01-01",
        end="2023-01-02",
    )

    assert frame["doc_id"].tolist() == ["SAME", "SAME"]
    receipt = manifest["duplicate_document_observations"]
    assert receipt["duplicate_doc_id_count"] == 1
    assert receipt["duplicate_observation_rows"] == 2
    assert receipt["eligible_duplicate_doc_id_count"] == 1
    assert len(receipt["duplicate_observation_sha256"]) == 64


def test_snapshot_rejects_duplicate_doc_id_with_conflicting_submit_datetime(tmp_path):
    _write_day(
        tmp_path,
        "2023-01-01",
        [{"docID": "SAME", "docTypeCode": "120", "submitDateTime": "2023-01-01 09:00"}],
    )
    _write_day(
        tmp_path,
        "2023-01-02",
        [{"docID": "SAME", "docTypeCode": "120", "submitDateTime": "2023-01-02 09:00"}],
    )

    with pytest.raises(ValueError, match="conflicting submit_datetime"):
        freeze_metadata_snapshot(tmp_path, start="2023-01-01", end="2023-01-02")


def test_snapshot_rejects_duplicate_eligible_doc_id_with_conflicting_doc_type(tmp_path):
    _write_day(
        tmp_path,
        "2023-01-01",
        [{"docID": "SAME", "docTypeCode": "120", "submitDateTime": "2023-01-01 09:00"}],
    )
    _write_day(
        tmp_path,
        "2023-01-02",
        [{"docID": "SAME", "docTypeCode": "130", "submitDateTime": "2023-01-01 09:00"}],
    )

    with pytest.raises(ValueError, match="conflicting doc_type_code"):
        freeze_metadata_snapshot(tmp_path, start="2023-01-01", end="2023-01-02")


def test_snapshot_skips_documented_null_tombstone_and_records_receipt(tmp_path):
    _write_day(
        tmp_path,
        "2023-01-01",
        [
            {
                "docID": "S-TOMBSTONE",
                "docTypeCode": None,
                "submitDateTime": None,
                "withdrawalStatus": "2",
                "parentDocID": "S-PARENT",
                "disclosureStatus": "0",
                "xbrlFlag": "0",
                "pdfFlag": "0",
                "attachDocFlag": "0",
                "englishDocFlag": "0",
                "csvFlag": "0",
                "legalStatus": "0",
            },
            {
                "docID": "S1001",
                "docTypeCode": "120",
                "submitDateTime": "2023-01-01 09:10",
            },
        ],
    )

    frame, manifest = freeze_metadata_snapshot(
        tmp_path,
        start="2023-01-01",
        end="2023-01-01",
    )

    assert frame["doc_id"].tolist() == ["S1001"]
    excluded = manifest["excluded_document_list_rows"]
    assert excluded["edinet_null_tombstone_count"] == 1
    assert len(excluded["edinet_null_tombstone_sha256"]) == 64


def test_snapshot_still_fails_closed_on_non_tombstone_missing_submit_datetime(tmp_path):
    _write_day(
        tmp_path,
        "2023-01-01",
        [
            {
                "docID": "S-BAD",
                "docTypeCode": "120",
                "submitDateTime": None,
                "disclosureStatus": "0",
                "xbrlFlag": "1",
                "pdfFlag": "1",
                "attachDocFlag": "0",
                "englishDocFlag": "0",
                "csvFlag": "1",
                "legalStatus": "1",
            }
        ],
    )

    with pytest.raises(ValueError, match="missing docID/docTypeCode/submitDateTime"):
        freeze_metadata_snapshot(tmp_path, start="2023-01-01", end="2023-01-01")


def test_snapshot_skips_real_timestamped_inert_tombstone_shape(tmp_path):
    _write_day(
        tmp_path,
        "2023-01-10",
        [
            {
                "seqNumber": 293,
                "docID": "S100PXGH",
                "edinetCode": None,
                "secCode": None,
                "JCN": None,
                "filerName": None,
                "fundCode": None,
                "ordinanceCode": None,
                "formCode": None,
                "docTypeCode": None,
                "periodStart": None,
                "periodEnd": None,
                "submitDateTime": "2023-01-10 15:30",
                "docDescription": None,
                "issuerEdinetCode": None,
                "subjectEdinetCode": None,
                "subsidiaryEdinetCode": None,
                "currentReportReason": None,
                "parentDocID": "S100PV94",
                "opeDateTime": None,
                "withdrawalStatus": "1",
                "docInfoEditStatus": "0",
                "disclosureStatus": "0",
                "xbrlFlag": "0",
                "pdfFlag": "0",
                "attachDocFlag": "0",
                "englishDocFlag": "0",
                "csvFlag": "0",
                "legalStatus": "0",
            },
            {
                "docID": "S100VALID",
                "docTypeCode": "120",
                "submitDateTime": "2023-01-10 15:31",
            },
        ],
    )

    frame, manifest = freeze_metadata_snapshot(
        tmp_path,
        start="2023-01-10",
        end="2023-01-10",
    )

    assert frame["doc_id"].tolist() == ["S100VALID"]
    excluded = manifest["excluded_document_list_rows"]
    assert excluded["edinet_null_tombstone_count"] == 1
