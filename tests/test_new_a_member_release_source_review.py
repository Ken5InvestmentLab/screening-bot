import copy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
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
        self.assertEqual(result["schema"], "NEW_A_MEMBER_RELEASE_SOURCE_REVIEW_V1")
        self.assertEqual(result["reviewed_diff_sha256"], hashlib.sha256(b"test patch").hexdigest())

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


class PresentationSuccessorReviewTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="new-a-member-presentation-")
        self.addCleanup(temp.cleanup)
        self.repo = Path(temp.name)
        self.git("init", "-q")
        self.git("config", "core.autocrlf", "false")
        for path in review.acceptance.AUTH_FILES:
            self.write(path, path.encode())
        self.config = {
            "name": review.acceptance.SERVICE, "d1_databases": [review.MEMBER_BINDING],
            "vars": {"CLOUD_MEMBER_VIEW_ENABLED": "true", "DISCORD_ALLOWED_ROLE_IDS": "fixed"}, "env": {},
        }
        self.write(review.CONFIG, json.dumps(self.config).encode())
        self.write(review.PRESENTATION, b"original presentation " + review._PURCHASE_LABEL + b"\n")
        self.prepare_path = "weak_early_beta/new_a/member_ordinary_acceptance.py"
        self.write(self.prepare_path, b"original approval\n")
        self.baseline = self.commit("Approved member baseline")

    def write(self, name, data):
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def git(self, *args):
        return subprocess.check_output(
            ["git", "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
             "-c", "commit.gpgsign=false", *args], cwd=self.repo,
        ).decode().strip()

    def commit(self, title):
        self.git("add", "-A")
        self.git("commit", "-qm", title)
        return self.git("rev-parse", "HEAD")

    def purchase_copy(self):
        self.write(review.PRESENTATION, b"original presentation " + review._NEW_PURCHASE_LABEL + b"\n")

    def test_exact_purchase_text_and_maintainer_changes_use_full_index_scope(self):
        self.purchase_copy()
        self.write(self.prepare_path, b"reviewed recursive improvement\n")
        candidate = self.commit("Presentation and scoped verifier")
        result = review.review_member_release_source(self.repo, self.baseline, candidate)
        self.assertEqual(result["schema"], review.PRESENTATION_REVIEW_SCHEMA)
        self.assertTrue(result["member_support_configured"])
        self.assertEqual(result["member_database_id"], review.MEMBER_BINDING["database_id"])
        self.git("config", "core.abbrev", "19")
        self.assertEqual(review.review_member_release_source(self.repo, self.baseline, candidate), result)
        self.write(self.prepare_path, b"another reviewed improvement\n")
        changed = self.commit("Different verifier bytes")
        self.assertNotEqual(review.review_member_release_source(self.repo, self.baseline, changed)["reviewed_diff_sha256"],
                            result["reviewed_diff_sha256"])

    def test_rejects_other_paths_copy_and_auth_configuration(self):
        for name, data, error in (
            (review.ENTRY, b"other authentication", "authorization"),
            (review.CONFIG, json.dumps({**self.config, "vars": {}}).encode(), "Worker configuration"),
            (review.PRESENTATION, review._NEW_PURCHASE_LABEL + b" changed unrelated UI", "approved purchase label"),
            ("other.txt", b"unexpected file", "mode or inventory"),
        ):
            with self.subTest(path=name):
                self.git("reset", "--hard", self.baseline)
                self.purchase_copy()
                self.write(name, data)
                candidate = self.commit("Rejected candidate")
                with self.assertRaisesRegex(ValueError, error):
                    review.review_member_release_source(self.repo, self.baseline, candidate)
