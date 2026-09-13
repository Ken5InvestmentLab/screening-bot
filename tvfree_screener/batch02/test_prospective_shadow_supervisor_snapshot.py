from __future__ import annotations

import unittest

from tvfree_screener.batch02.prospective_shadow_supervisor_snapshot import build_snapshot


ALL_TRUE = {
    "representation_gate_passed": True,
    "supervised_evaluation_preregistered": True,
    "h1_policy_frozen": True,
    "model_freeze_manifest_valid": True,
    "model_spec_sha_pinned": True,
    "candidate_export_contract_satisfied": True,
    "causal_preflight_passed": True,
    "append_only_integrity_enabled": True,
    "production_isolation_confirmed": True,
    "historical_2026_tuning_forbidden": True,
}


class SupervisorSnapshotTests(unittest.TestCase):
    def item(self, cid="A", lane="event", readiness=None):
        return {
            "candidate_id": cid,
            "lane": lane,
            "source_branch": "research/example",
            "source_commit": "abc123",
            "readiness": dict(ALL_TRUE if readiness is None else readiness),
        }

    def test_ready_candidate_is_allowed(self):
        out = build_snapshot([self.item()])
        self.assertEqual(out["ready_candidate_ids"], ["A"])
        self.assertEqual(out["blocked_candidate_ids"], [])

    def test_missing_requirement_blocks(self):
        r = dict(ALL_TRUE)
        r["h1_policy_frozen"] = False
        out = build_snapshot([self.item(readiness=r)])
        self.assertEqual(out["blocked_candidate_ids"], ["A"])
        self.assertIn("h1_policy_frozen", out["candidates"][0]["missing_requirements"])

    def test_duplicate_candidate_id_rejected(self):
        with self.assertRaises(ValueError):
            build_snapshot([self.item("A"), self.item("A", "core")])

    def test_return_field_at_top_level_rejected(self):
        x = self.item()
        x["ret5bd_gross"] = 0.10
        with self.assertRaises(ValueError):
            build_snapshot([x])

    def test_return_field_inside_readiness_rejected(self):
        x = self.item()
        x["readiness"]["net_mean"] = 0.02
        with self.assertRaises(ValueError):
            build_snapshot([x])

    def test_multiple_lanes_are_counted_without_ranking(self):
        out = build_snapshot([
            self.item("E", "event"),
            self.item("C", "core"),
            self.item("S", "consensus"),
        ])
        self.assertEqual(out["candidate_count"], 3)
        self.assertEqual(out["lane_counts"], {"consensus": 1, "core": 1, "event": 1})
        self.assertFalse(out["integrity"]["ranks_candidates"])
        self.assertFalse(out["integrity"]["selects_best_candidate"])

    def test_candidate_id_required(self):
        x = self.item()
        x["candidate_id"] = ""
        with self.assertRaises(ValueError):
            build_snapshot([x])

    def test_lane_required(self):
        x = self.item()
        x["lane"] = ""
        with self.assertRaises(ValueError):
            build_snapshot([x])


if __name__ == "__main__":
    unittest.main()
