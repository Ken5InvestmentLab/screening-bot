from prospective_shadow_admission_gate import evaluate_shadow_admission


MANIFEST = {
    "experiment_id": "EXP-A",
    "model_freeze_id": "FREEZE-A",
    "frozen_at": "2026-09-13T15:00:00+09:00",
}


def row(**kw):
    base = {
        "experiment_id": "EXP-A",
        "model_freeze_id": "FREEZE-A",
        "symbol": "1234.T",
        "signal_date": "2026-09-14",
        "bin_name": "AM_09_13",
        "feature_cutoff": "2026-09-14T13:00:00+09:00",
        "source_tag": "RAW_CAUSAL_INTRADAY",
        "rank": 1,
    }
    base.update(kw)
    return base


def test_valid_batch_admitted():
    out = evaluate_shadow_admission(MANIFEST, [row()])
    assert out["admitted"] is True
    assert out["decision"] == "ADMIT_PROSPECTIVE_SHADOW_BATCH"


def test_noncausal_source_blocks():
    out = evaluate_shadow_admission(MANIFEST, [row(source_tag="POSTCLOSE_RECON_ONLY")])
    assert out["admitted"] is False
    assert any(x.startswith("causal_preflight_failed:") for x in out["errors"])


def test_pre_freeze_cutoff_blocks():
    r = row(signal_date="2026-09-13", bin_name="AM_09_13", feature_cutoff="2026-09-13T13:00:00+09:00")
    out = evaluate_shadow_admission(MANIFEST, [r])
    assert out["admitted"] is False
    assert "postfreeze_guard_failed" in out["errors"]


def test_empty_batch_blocks():
    out = evaluate_shadow_admission(MANIFEST, [])
    assert out["admitted"] is False
    assert "postfreeze_guard_failed" in out["errors"]


def test_duplicate_candidate_key_blocks():
    r = row()
    out = evaluate_shadow_admission(MANIFEST, [r, dict(r)])
    assert out["admitted"] is False
    assert any(x.startswith("causal_preflight_failed:") for x in out["errors"])


def test_wrong_bin_cutoff_blocks():
    out = evaluate_shadow_admission(MANIFEST, [row(feature_cutoff="2026-09-14T12:59:00+09:00")])
    assert out["admitted"] is False
    assert any(x.startswith("causal_preflight_failed:") for x in out["errors"])


def test_freeze_identity_mismatch_blocks():
    out = evaluate_shadow_admission(MANIFEST, [row(model_freeze_id="FREEZE-B")])
    assert out["admitted"] is False
    assert "postfreeze_guard_failed" in out["errors"]


def test_integrity_declares_atomic_dual_gate():
    out = evaluate_shadow_admission(MANIFEST, [row()])
    assert out["integrity"]["requires_both_causal_and_postfreeze_checks"] is True
    assert out["integrity"]["batch_is_atomic"] is True
    assert out["integrity"]["production_modified"] is False
