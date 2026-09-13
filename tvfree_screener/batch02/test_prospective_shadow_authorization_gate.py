from prospective_shadow_authorization_gate import evaluate_authorization


def _src(branch: str, head: str = "a" * 40, **overrides):
    row = {
        "branch": branch,
        "readiness_ok": True,
        "staleness_ok": True,
        "ancestry_ok": True,
        "current_head": head,
        "observed_head": head,
    }
    row.update(overrides)
    return row


def _base():
    sha = "f" * 64
    return {
        "sources": [
            _src("research/tvfree-canonical-batch02"),
            _src("research/tentei-cloud-mtf", "b" * 40),
            _src("research/consensus-atr-regime-gate", "c" * 40),
        ],
        "supervisor_contract_sha256": sha,
        "expected_supervisor_contract_sha256": sha,
        "all_heads_refetched_immediately_before_authorization": True,
        "production_isolation_confirmed": True,
        "historical_2026_tuning_forbidden": True,
    }


def test_all_ok_authorizes():
    r = evaluate_authorization(_base())
    assert r["authorized_for_prospective_shadow_start"] is True
    assert r["decision"] == "AUTHORIZE_PROSPECTIVE_SHADOW_START"
    assert r["blockers"] == []


def test_stale_lane_blocks():
    p = _base()
    p["sources"][2]["staleness_ok"] = False
    r = evaluate_authorization(p)
    assert not r["authorized_for_prospective_shadow_start"]
    assert "stale_snapshot:research/consensus-atr-regime-gate" in r["blockers"]


def test_head_not_pinned_blocks_even_if_other_flags_true():
    p = _base()
    p["sources"][1]["current_head"] = "d" * 40
    r = evaluate_authorization(p)
    assert "head_not_pinned:research/tentei-cloud-mtf" in r["blockers"]


def test_supervisor_contract_mismatch_blocks():
    p = _base()
    p["expected_supervisor_contract_sha256"] = "0" * 64
    r = evaluate_authorization(p)
    assert "supervisor_contract_mismatch" in r["blockers"]


def test_missing_immediate_refetch_blocks():
    p = _base()
    p["all_heads_refetched_immediately_before_authorization"] = False
    r = evaluate_authorization(p)
    assert "source_heads_not_refetched_immediately_before_authorization" in r["blockers"]


def test_production_isolation_blocks():
    p = _base()
    p["production_isolation_confirmed"] = False
    r = evaluate_authorization(p)
    assert "production_isolation_not_confirmed" in r["blockers"]


def test_missing_branch_blocks():
    p = _base()
    p["sources"] = p["sources"][:-1]
    r = evaluate_authorization(p)
    assert "research/consensus-atr-regime-gate" in r["missing_source_branches"]
    assert "missing_source_branch:research/consensus-atr-regime-gate" in r["blockers"]


def test_gate_never_promotes_or_uses_returns():
    r = evaluate_authorization(_base())
    assert r["integrity"]["uses_strategy_returns"] is False
    assert r["integrity"]["ranks_candidates"] is False
    assert r["integrity"]["production_modified"] is False
