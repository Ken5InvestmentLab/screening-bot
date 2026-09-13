from tvfree_screener.batch02.prospective_shadow_snapshot_staleness import evaluate_staleness


def row(candidate_id="event", branch="research/event", head="abc", ready=True):
    return {
        "candidate_id": candidate_id,
        "branch": branch,
        "observed_head": head,
        "ready_for_prospective_shadow": ready,
    }


def test_fresh_ready_candidate_remains_allowed():
    out = evaluate_staleness({"candidates": [row()]}, {"research/event": "abc"})
    assert out["decision"] == "SNAPSHOT_FRESH"
    assert out["candidates"][0]["prospective_shadow_start_allowed_from_this_snapshot"] is True


def test_advanced_head_makes_snapshot_stale_and_blocks_start():
    out = evaluate_staleness({"candidates": [row()]}, {"research/event": "def"})
    assert out["decision"] == "REFRESH_STALE_READINESS"
    assert out["candidates"][0]["reason"] == "BRANCH_HEAD_ADVANCED"
    assert out["candidates"][0]["prospective_shadow_start_allowed_from_this_snapshot"] is False


def test_missing_current_head_is_stale():
    out = evaluate_staleness({"candidates": [row()]}, {})
    assert out["candidates"][0]["reason"] == "CURRENT_HEAD_UNAVAILABLE"
    assert out["stale_count"] == 1


def test_not_ready_never_becomes_allowed_even_when_fresh():
    out = evaluate_staleness({"candidates": [row(ready=False)]}, {"research/event": "abc"})
    assert out["decision"] == "SNAPSHOT_FRESH"
    assert out["candidates"][0]["prospective_shadow_start_allowed_from_this_snapshot"] is False


def test_mixed_candidates_count_fresh_and_stale():
    snap = {"candidates": [
        row("event", "research/event", "a"),
        row("core", "research/core", "b"),
        row("consensus", "research/consensus", "c"),
    ]}
    out = evaluate_staleness(snap, {
        "research/event": "a",
        "research/core": "B2",
        "research/consensus": "c",
    })
    assert out["candidate_count"] == 3
    assert out["fresh_count"] == 2
    assert out["stale_count"] == 1


def test_no_return_or_performance_fields_are_required():
    out = evaluate_staleness({"candidates": [row()]}, {"research/event": "abc"})
    assert out["opens_strategy_returns"] is False
    assert out["selection_or_threshold_tuning_allowed"] is False
