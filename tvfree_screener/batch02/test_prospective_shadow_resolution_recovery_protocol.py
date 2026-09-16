from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tvfree_screener.batch02.prospective_shadow_resolution_recovery_protocol import (
    build_recovery_record,
    write_immutable_recovery_record,
)


class ResolutionRecoveryProtocolTest(unittest.TestCase):
    def test_sidecar_ahead_emits_outcome_blind_recovery_evidence(self):
        chain = [
            {"resolved_output_sha256": "aaa"},
            {"resolved_output_sha256": "bbb"},
        ]
        before = repr(chain)
        record = build_recovery_record(chain, "aaa", chain_valid=True)
        self.assertEqual(record["state"], "sidecar_ahead_interrupted")
        self.assertTrue(record["recovery_allowed"])
        self.assertFalse(record["strategy_outcomes_opened"])
        self.assertFalse(record["gross_returns_computed"])
        self.assertFalse(record["immutable_chain_rewritten"])
        self.assertEqual(repr(chain), before)

    def test_tampered_chain_is_not_recoverable(self):
        record = build_recovery_record(
            [{"resolved_output_sha256": "aaa"}],
            "aaa",
            chain_valid=False,
        )
        self.assertEqual(record["state"], "invalid_tampered")
        self.assertFalse(record["recovery_allowed"])

    def test_record_is_append_only_and_exact_replay_is_idempotent(self):
        record = build_recovery_record(
            [{"resolved_output_sha256": "aaa"}],
            "aaa",
            chain_valid=True,
        )
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "recovery.json"
            write_immutable_recovery_record(path, record)
            first = path.read_bytes()
            write_immutable_recovery_record(path, record)
            self.assertEqual(path.read_bytes(), first)
            changed = dict(record)
            changed["reason"] = "changed"
            with self.assertRaises(FileExistsError):
                write_immutable_recovery_record(path, changed)
            self.assertEqual(path.read_bytes(), first)

    def test_record_hash_is_deterministic(self):
        chain = [{"resolved_output_sha256": "aaa"}]
        a = build_recovery_record(chain, "aaa", chain_valid=True)
        b = build_recovery_record(chain, "AAA", chain_valid=True)
        self.assertEqual(a["record_sha256"], b["record_sha256"])
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))


if __name__ == "__main__":
    unittest.main()
