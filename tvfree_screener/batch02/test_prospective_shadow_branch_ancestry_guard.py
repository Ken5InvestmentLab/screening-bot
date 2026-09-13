from tvfree_screener.batch02.prospective_shadow_branch_ancestry_guard import evaluate_branch_ancestry


def snap(branch="research/x", head="aaa"):
    return {"branch": branch, "observed_head": head}


def cur(status, head="bbb", branch="research/x", ahead_by=None, behind_by=None):
    out = {"branch": branch, "current_head": head, "compare_status": status}
    if ahead_by is not None:
        out["ahead_by"] = ahead_by
    if behind_by is not None:
        out["behind_by"] = behind_by
    return out


def test_identical_allows_existing_snapshot():
    r = evaluate_branch_ancestry(snap(head="aaa"), cur("identical", head="aaa"))
    assert r["decision"] == "ALLOW_EXISTING_READINESS_SNAPSHOT"
    assert r["readiness_snapshot_still_current"] is True


def test_ahead_requires_refresh_but_is_fast_forward():
    r = evaluate_branch_ancestry(snap(), cur("ahead"))
    assert r["decision"] == "REFRESH_READINESS_AFTER_FAST_FORWARD"
    assert r["fast_forward_only"] is True
    assert r["readiness_snapshot_still_current"] is False


def test_behind_blocks_rewind():
    r = evaluate_branch_ancestry(snap(), cur("behind"))
    assert r["decision"] == "BLOCK_AND_RECONCILE_BRANCH_HISTORY"
    assert "BRANCH_REWIND_DETECTED" in r["errors"]


def test_diverged_blocks():
    r = evaluate_branch_ancestry(snap(), cur("diverged"))
    assert r["decision"] == "BLOCK_AND_RECONCILE_BRANCH_HISTORY"
    assert "BRANCH_HISTORY_DIVERGED" in r["errors"]


def test_unknown_blocks():
    r = evaluate_branch_ancestry(snap(), cur(None))
    assert r["decision"] == "BLOCK_AND_RECONCILE_BRANCH_HISTORY"
    assert "ANCESTRY_UNVERIFIED" in r["errors"]


def test_branch_identity_mismatch_blocks():
    r = evaluate_branch_ancestry(snap(branch="research/a"), cur("identical", head="aaa", branch="research/b"))
    assert r["decision"] == "BLOCK_AND_RECONCILE_BRANCH_HISTORY"
    assert "BRANCH_IDENTITY_MISMATCH" in r["errors"]


def test_counts_can_infer_divergence():
    r = evaluate_branch_ancestry(snap(), cur(None, ahead_by=2, behind_by=1))
    assert r["relation"] == "DIVERGED"
    assert r["decision"] == "BLOCK_AND_RECONCILE_BRANCH_HISTORY"
