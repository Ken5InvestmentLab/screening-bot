import copy
import json
import unittest
from unittest.mock import patch

from weak_early_beta.new_a import member_release_source_review as review


BEFORE = "a" * 40
AFTER = "b" * 40
OLD_ENTRY = b"""import { passiveObservationSink } from './owner-observation-d1';
  async fetch(request, env) {
    const denied = await ownerOnlyGate(request, env);
    if (denied) return denied;
    return ownerOnlyContents(request);
  }
"""
NEW_ENTRY = (b"import {memberRouteCandidate} from './new-a-role-integration';\n" + OLD_ENTRY).replace(
    b"if (denied) return denied;",
    b"if (denied) return (await memberRouteCandidate(request, env, denied, operationalBuild)) ?? denied;",
)


class MemberReleaseSourceReviewTest(unittest.TestCase):
    def setUp(self):
        self.old_config = {"d1_databases": [], "vars": {"DISCORD_ALLOWED_ROLE_IDS": "fixed"}, "env": {}}
        self.new_config = copy.deepcopy(self.old_config)
        self.new_config["vars"]["CLOUD_MEMBER_VIEW_ENABLED"] = "false"
        self.new_config["d1_databases"].append(review.MEMBER_BINDING.copy())
        self.source_after = NEW_ENTRY
        self.changed_protected = None
        mock = patch.object(review, "git", side_effect=self.git)
        mock.start()
        self.addCleanup(mock.stop)

    def git(self, _repo, op, *args):
        if op == "merge-base":
            return BEFORE.encode()
        if op == "diff":
            return b"test patch"
        revision, path = args[0].split(":", 1)
        old = revision == BEFORE
        if path == review.CONFIG:
            return json.dumps(self.old_config if old else self.new_config).encode()
        if path == review.ENTRY:
            return OLD_ENTRY if old else self.source_after
        return b"altered protected source" if path == self.changed_protected and not old else path.encode()

    def inspect(self):
        return review.review_member_release_source(".", BEFORE, AFTER)

    def test_only_member_fallback_and_exact_dedicated_binding_pass(self):
        result = self.inspect()
        self.assertTrue(result["owner_only_gate_preserved"])
        self.assertFalse(result["member_support_configured"])
        self.assertEqual(result["candidate_source"], AFTER)

    def test_refuses_any_additional_owner_or_auth_change(self):
        self.source_after = NEW_ENTRY.replace(b"ownerOnlyContents", b"memberContents")
        with self.assertRaisesRegex(ValueError, "more than"):
            self.inspect()
        self.source_after = NEW_ENTRY
        self.changed_protected = "weak-early-beta-gate/src/cloud-owner-only.ts"
        with self.assertRaisesRegex(ValueError, "changed beyond"):
            self.inspect()

    def test_refuses_role_change_or_another_d1(self):
        self.new_config["vars"]["DISCORD_ALLOWED_ROLE_IDS"] = "different"
        with self.assertRaisesRegex(ValueError, "existing production"):
            self.inspect()
        self.new_config["vars"]["DISCORD_ALLOWED_ROLE_IDS"] = "fixed"
        self.new_config["d1_databases"][0]["database_id"] = "different"
        with self.assertRaisesRegex(ValueError, "D1 binding"):
            self.inspect()
