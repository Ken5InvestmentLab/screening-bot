import json
import zipfile
from pathlib import Path

import pytest

from edinet_selected_zip_freeze import freeze_selected_zips


def _zip(path: Path, name: str = "xbrl/a.txt", payload: bytes = b"ok") -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(name, payload)


def _receipt(ids=None):
    return {
        "selected_doc_ids": ids or ["S100AAA1", "S100AAA2"],
        "strategy_outcomes_opened": False,
        "no_replacement_rule": True,
    }


def test_freezes_exact_selected_zip_set_without_opening_outputs(tmp_path: Path):
    _zip(tmp_path / "S100AAA1.zip")
    _zip(tmp_path / "S100AAA2.zip", payload=b"different")
    out = freeze_selected_zips(_receipt(), tmp_path)
    assert out["status"] == "SELECTED_ZIPS_FROZEN_OUTCOME_BLIND"
    assert out["selected_doc_ids"] == ["S100AAA1", "S100AAA2"]
    assert out["strategy_outcomes_opened"] is False
    assert out["parser_outputs_opened"] is False
    assert out["no_replacement_rule"] is True
    assert len(out["aggregate_sha256_chain"]) == 64
    assert all(len(x["sha256"]) == 64 for x in out["files"])


def test_missing_selected_zip_fails_closed(tmp_path: Path):
    _zip(tmp_path / "S100AAA1.zip")
    with pytest.raises(ValueError, match="set mismatch"):
        freeze_selected_zips(_receipt(), tmp_path)


def test_extra_zip_fails_closed_to_prevent_replacement_or_drift(tmp_path: Path):
    _zip(tmp_path / "S100AAA1.zip")
    _zip(tmp_path / "S100AAA2.zip")
    _zip(tmp_path / "S100OTHER.zip")
    with pytest.raises(ValueError, match="set mismatch"):
        freeze_selected_zips(_receipt(), tmp_path)


def test_invalid_or_empty_zip_fails_closed(tmp_path: Path):
    (tmp_path / "S100AAA1.zip").write_bytes(b"not-a-zip")
    _zip(tmp_path / "S100AAA2.zip")
    with pytest.raises(ValueError, match="not a valid ZIP"):
        freeze_selected_zips(_receipt(), tmp_path)


def test_sample_receipt_must_keep_outcomes_closed_and_no_replacement(tmp_path: Path):
    _zip(tmp_path / "S100AAA1.zip")
    _zip(tmp_path / "S100AAA2.zip")
    r = _receipt()
    r["strategy_outcomes_opened"] = True
    with pytest.raises(ValueError, match="strategy_outcomes_opened=false"):
        freeze_selected_zips(r, tmp_path)
    r = _receipt()
    r["no_replacement_rule"] = False
    with pytest.raises(ValueError, match="no_replacement_rule=true"):
        freeze_selected_zips(r, tmp_path)


def test_duplicate_doc_ids_fail_closed(tmp_path: Path):
    _zip(tmp_path / "S100AAA1.zip")
    with pytest.raises(ValueError, match="duplicate"):
        freeze_selected_zips(_receipt(["S100AAA1", "S100AAA1"]), tmp_path)
