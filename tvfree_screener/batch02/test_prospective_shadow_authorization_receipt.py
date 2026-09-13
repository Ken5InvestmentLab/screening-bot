from prospective_shadow_authorization_receipt import (
    build_authorization_receipt,
    verify_authorization_receipt,
)


def auth(decision="AUTHORIZE_PROSPECTIVE_SHADOW_START"):
    return {
        "decision": decision,
        "authorized": decision == "AUTHORIZE_PROSPECTIVE_SHADOW_START",
        "checks": {"all_source_heads_refetched_immediately_before_authorization": True},
    }


def heads():
    return {
        "research/consensus-atr-regime-gate": "c" * 40,
        "research/tentei-cloud-mtf": "b" * 40,
        "research/tvfree-canonical-batch02": "a" * 40,
    }


def test_roundtrip_verifies():
    r = build_authorization_receipt(auth(), heads(), "d" * 64, "2026-09-14T01:07:00+09:00")
    out = verify_authorization_receipt(r, auth(), heads(), "d" * 64)
    assert out["valid"] is True


def test_head_change_invalidates():
    r = build_authorization_receipt(auth(), heads(), "d" * 64, "2026-09-14T01:07:00+09:00")
    h = heads(); h["research/tentei-cloud-mtf"] = "e" * 40
    out = verify_authorization_receipt(r, auth(), h, "d" * 64)
    assert "source_branch_heads_mismatch" in out["errors"]


def test_contract_change_invalidates():
    r = build_authorization_receipt(auth(), heads(), "d" * 64, "2026-09-14T01:07:00+09:00")
    out = verify_authorization_receipt(r, auth(), heads(), "e" * 64)
    assert "supervisor_contract_sha256_mismatch" in out["errors"]


def test_authorization_result_change_invalidates():
    r = build_authorization_receipt(auth(), heads(), "d" * 64, "2026-09-14T01:07:00+09:00")
    out = verify_authorization_receipt(r, auth("BLOCK_PROSPECTIVE_SHADOW_START"), heads(), "d" * 64)
    assert "authorization_result_sha256_mismatch" in out["errors"]


def test_receipt_tamper_invalidates_self_hash():
    r = build_authorization_receipt(auth(), heads(), "d" * 64, "2026-09-14T01:07:00+09:00")
    r["created_at"] = "2026-09-14T01:08:00+09:00"
    out = verify_authorization_receipt(r, auth(), heads(), "d" * 64)
    assert "receipt_sha256_mismatch" in out["errors"]


def test_invalid_head_rejected_on_create():
    h = heads(); h["research/tentei-cloud-mtf"] = "short"
    try:
        build_authorization_receipt(auth(), h, "d" * 64, "2026-09-14T01:07:00+09:00")
    except ValueError:
        return
    assert False, "expected ValueError"


def test_receipt_never_authorizes_production():
    r = build_authorization_receipt(auth(), heads(), "d" * 64, "2026-09-14T01:07:00+09:00")
    assert r["production_authorized"] is False
