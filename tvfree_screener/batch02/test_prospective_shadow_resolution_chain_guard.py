from __future__ import annotations

import hashlib
import json
import unittest

from prospective_shadow_resolution_chain_guard import build_chain_link, verify_chain


def _sha_payload(payload) -> str:
    raw = (json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _resolution_receipt(*, created_at: str, resolved_output_sha256: str, nonce: str) -> dict:
    body = {
        "receipt_type": "PROSPECTIVE_SHADOW_RESOLUTION_RECEIPT",
        "schema_version": 2,
        "created_at": created_at,
        "experiment_id": "EXP",
        "model_freeze_id": "FREEZE",
        "resolved_output_sha256": resolved_output_sha256,
        "nonce": nonce,
        "production_authorized": False,
    }
    body["receipt_sha256"] = _sha_payload(body)
    return body


class ResolutionChainGuardTests(unittest.TestCase):
    def _chain(self):
        r1 = _resolution_receipt(created_at="2026-09-15T07:00:00+09:00", resolved_output_sha256="a" * 64, nonce="one")
        l1 = build_chain_link(resolution_receipt=r1)
        r2 = _resolution_receipt(created_at="2026-09-15T08:00:00+09:00", resolved_output_sha256="b" * 64, nonce="two")
        l2 = build_chain_link(resolution_receipt=r2, previous_link=l1)
        return r1, l1, r2, l2

    def test_valid_cross_run_chain_passes(self):
        _, l1, _, l2 = self._chain()
        out = verify_chain([l1, l2])
        self.assertTrue(out["valid"])
        self.assertEqual(out["links"], 2)

    def test_replayed_resolution_receipt_is_blocked(self):
        r1, l1, _, _ = self._chain()
        replay = dict(r1)
        replay["created_at"] = "2026-09-15T09:00:00+09:00"
        replay["receipt_sha256"] = _sha_payload({k: v for k, v in replay.items() if k != "receipt_sha256"})
        with self.assertRaisesRegex(ValueError, "resolved output replay"):
            build_chain_link(resolution_receipt=replay, previous_link=l1)

    def test_historical_output_rollback_is_blocked_across_nonadjacent_links(self):
        _, l1, _, l2 = self._chain()
        r3 = _resolution_receipt(created_at="2026-09-15T09:00:00+09:00", resolved_output_sha256="a" * 64, nonce="three")
        l3 = build_chain_link(resolution_receipt=r3, previous_link=l2)
        out = verify_chain([l1, l2, l3])
        self.assertFalse(out["valid"])
        self.assertIn("link_2:resolved_output_rollback_or_replay", out["errors"])

    def test_previous_chain_link_tamper_is_blocked(self):
        _, l1, _, l2 = self._chain()
        tampered = dict(l2)
        tampered["previous_chain_link_sha256"] = "0" * 64
        body = dict(tampered)
        body.pop("chain_link_sha256", None)
        tampered["chain_link_sha256"] = _sha_payload(body)
        out = verify_chain([l1, tampered])
        self.assertFalse(out["valid"])
        self.assertIn("link_1:previous_chain_link_sha256_mismatch", out["errors"])

    def test_time_rollback_is_blocked(self):
        _, l1, _, _ = self._chain()
        r2 = _resolution_receipt(created_at="2026-09-15T06:59:59+09:00", resolved_output_sha256="c" * 64, nonce="old")
        with self.assertRaisesRegex(ValueError, "strictly increase"):
            build_chain_link(resolution_receipt=r2, previous_link=l1)

    def test_identity_change_is_blocked(self):
        _, l1, r2, _ = self._chain()
        changed = dict(r2)
        changed["model_freeze_id"] = "OTHER"
        changed["receipt_sha256"] = _sha_payload({k: v for k, v in changed.items() if k != "receipt_sha256"})
        with self.assertRaisesRegex(ValueError, "identity changed"):
            build_chain_link(resolution_receipt=changed, previous_link=l1)

    def test_chain_link_self_hash_tamper_is_blocked(self):
        _, l1, _, l2 = self._chain()
        tampered = dict(l2)
        tampered["note"] = "tampered"
        out = verify_chain([l1, tampered])
        self.assertFalse(out["valid"])
        self.assertIn("link_1:chain_link_sha256_mismatch", out["errors"])


if __name__ == "__main__":
    unittest.main()
