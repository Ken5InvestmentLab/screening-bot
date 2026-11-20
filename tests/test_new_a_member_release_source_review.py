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


    def test_only_confirmed_completion_cutoffs_and_durable_guide_are_reviewed(self):
        self.purchase_copy()
        deltas = {**review._COMPLETED_TIMING_DELTAS, review._TIMING_GUIDE: (review._TIMING_GUIDE_DELTA,)}
        old = {path: b"\n".join(before for before, _ in edits) for path, edits in deltas.items()}
        inclusive = {path: b"\n".join(after for _, after in edits) for path, edits in deltas.items()}
        for path, contents in old.items():
            self.write(path, contents)
        loader = "weak-early-beta-gate/scripts/new-a-ui-source/assets/member-loader.js"
        self.write(loader, b"original member loader")
        baseline = self.commit("Approved purchase copy and strict completion cutoff")
        for path, contents in inclusive.items():
            self.write(path, contents)
        candidate = self.commit("Permit confirmed same-session completion")
        result = review.review_member_release_source(self.repo, baseline, candidate)
        self.assertEqual(result["schema"], review.COMPLETED_TIMING_REVIEW_SCHEMA)
        self.git("config", "core.abbrev", "17")
        self.assertEqual(review.review_member_release_source(self.repo, baseline, candidate), result)

        self.write(review.PRESENTATION, b"dashboard cards " + review._NEW_PURCHASE_LABEL)
        self.write(loader, b"dashboard level controls")
        layout = self.commit("Review the dashboard and inclusive cutoff together")
        layout_result = review.review_member_release_source(self.repo, baseline, layout)
        self.assertEqual(layout_result["schema"], review.COMPLETED_TIMING_REVIEW_SCHEMA)
        self.assertNotEqual(layout_result["reviewed_diff_sha256"], result["reviewed_diff_sha256"])

        self.write(review.PRESENTATION, b"dashboard cards " + review._PURCHASE_LABEL)
        renamed = self.commit("Undo the approved purchase copy")
        with self.assertRaisesRegex(ValueError, "approved purchase link or label"):
            review.review_member_release_source(self.repo, baseline, renamed)
        self.write(review.PRESENTATION, b"dashboard cards " + review._NEW_PURCHASE_LABEL)

        publisher = "weak_early_beta/new_a/member_publisher.py"
        self.write(publisher, old[publisher])
        partial = self.commit("Missing importer validator")
        with self.assertRaisesRegex(ValueError, "approved source scope"):
            review.review_member_release_source(self.repo, baseline, partial)

        self.write(publisher, inclusive[publisher] + b"\nOther data change")
        extra = self.commit("Changes outside the cutoff")
        with self.assertRaisesRegex(ValueError, "more than the inclusive cutoff"):
            review.review_member_release_source(self.repo, baseline, extra)

    def test_fundamentals_requires_exact_reviewed_files_and_only_the_approved_regular_migration(self):
        migration = review._FUNDAMENTAL_MIGRATION
        paths = review._FUNDAMENTAL_PRODUCT_PATHS | review._SUCCESSOR_REVIEW_PATHS
        for path in paths - {migration}:
            self.write(path, b"old " + path.encode())
        baseline = self.commit("Accepted dashboard")
        content = {path: b"reviewed " + path.encode() for path in paths}
        checked = hashlib.sha256()
        for path in sorted(review._FUNDAMENTAL_PRODUCT_PATHS):
            checked.update(path.encode() + b"\0" + hashlib.sha256(content[path]).digest())
        for path, data in content.items():
            self.write(path, data)
        candidate = self.commit("Exact reviewed fundamentals")
        with (patch.object(review, "_FUNDAMENTAL_BASELINE", baseline),
              patch.object(review, "_FUNDAMENTAL_PRODUCT_SHA256", checked.hexdigest())):
            result = review.review_member_release_source(self.repo, baseline, candidate)
            self.assertEqual(result["schema"], review.FUNDAMENTAL_REVIEW_SCHEMA)
            self.assertTrue(result["owner_only_gate_preserved"])
            self.assertEqual(result["member_database_id"], review.MEMBER_BINDING["database_id"])
            self.assertEqual(result["reviewed_diff_sha256"], hashlib.sha256(review.git(
                self.repo, "diff", "--binary", "--full-index", "--no-renames", "--no-ext-diff", "--no-textconv",
                "--no-color", "--src-prefix=a/", "--dst-prefix=b/", "--unified=3", "--diff-algorithm=myers",
                "--no-indent-heuristic", baseline, candidate, "--")).hexdigest())
            for path, unexpected, error in (
                (migration, b"alternate SQL", "migration bytes"),
                ("weak-early-beta-gate/src/new-a-role-facade.ts", b"different member auth", "reviewed product"),
                ("weak-early-beta-gate/member-migrations/0006_unreviewed.sql", b"another table", "mode or inventory"),
                (self.prepare_path, b"old " + self.prepare_path.encode(), "exact reviewed source scope"),
                (review.CONFIG, b"{}", "Worker configuration"),
                (review.ENTRY, b"different owner auth", "authorization"),
            ):
                with self.subTest(path=path):
                    self.git("reset", "--hard", candidate)
                    self.write(path, unexpected)
                    changed = self.commit("Unreviewed fundamental successor")
                    with self.assertRaisesRegex(ValueError, error):
                        review.review_member_release_source(self.repo, baseline, changed)
            self.git("reset", "--hard", candidate)
            self.git("update-index", "--chmod=+x", migration)
            self.git("commit", "-qm", "Make the added migration executable")
            with self.assertRaisesRegex(ValueError, "mode or inventory"):
                review.review_member_release_source(self.repo, baseline, self.git("rev-parse", "HEAD"))


    def test_role_only_successor_requires_the_exact_access_and_observation_delta(self):
        migration = review._ROLE_ONLY_MIGRATION
        old_config = json.dumps(self.config, indent=2).encode()
        self.write(review.CONFIG, old_config)
        for path in review._ROLE_ONLY_PRODUCT_PATHS - {migration}:
            self.write(path, b"old " + path.encode())
        baseline = self.commit("Accepted fundamental member release")

        config = old_config.replace(review._ROLE_ONLY_CONFIG_LINE,
                                    review._ROLE_ONLY_CONFIG_LINE + review._ROLE_ONLY_AUDIENCE_LINE)
        self.write(review.CONFIG, config)
        self.assertNotEqual(config, old_config)
        digest = hashlib.sha256()
        for path in sorted(review._ROLE_ONLY_PRODUCT_PATHS):
            contents = b"role-only " + path.encode()
            self.write(path, contents)
            digest.update(path.encode() + b"\0" + hashlib.sha256(contents).digest())
        candidate = self.commit("Role-only with dedicated response evidence")

        with (patch.object(review, "_ROLE_ONLY_BASELINE", baseline),
              patch.object(review, "_ROLE_ONLY_PRODUCT_SHA256", digest.hexdigest())):
            result = review.review_member_release_source(self.repo, baseline, candidate)
            self.assertEqual(result["schema"], review.ROLE_ONLY_REVIEW_SCHEMA)
            self.assertEqual(result["member_audience"], "role_only")
            self.assertTrue(result["owner_only_gate_preserved"])
            self.assertEqual(result["member_database_id"], review.MEMBER_BINDING["database_id"])
            for path, unexpected, error in (
                (review.CONFIG, old_config, "Worker configuration"),
                (review.CONFIG, config.replace(b'"fixed"', b'"other"'), "Worker configuration"),
                (review.ENTRY, b"different owner authorization", "authorization"),
                (migration, b"different response contract", "access or observation bytes"),
                ("weak_early_beta/new_a/new_run.py", b"unreviewed file", "mode or inventory"),
                ("weak-early-beta-gate/src/new-a-role-facade.ts", b"tiered fallback", "access or observation bytes"),
            ):
                with self.subTest(path=path, error=error):
                    self.git("reset", "--hard", candidate)
                    self.write(path, unexpected)
                    changed = self.commit("Unreviewed role-only successor")
                    with self.assertRaisesRegex(ValueError, error):
                        review.review_member_release_source(self.repo, baseline, changed)

    def test_journal_successor_pins_reviewed_parent_and_runner_bytes(self):
        self.config['vars']['CLOUD_MEMBER_AUDIENCE'] = 'role_only'
        self.write(review.CONFIG, json.dumps(self.config).encode())
        for path in review._JOURNAL_PRODUCT_PATHS | review._SUCCESSOR_REVIEW_PATHS:
            self.write(path, b'prior ' + path.encode())
        baseline = self.commit('Accepted role-only baseline')
        for path in review._JOURNAL_PRODUCT_PATHS:
            self.write(path, b'reviewed runner ' + path.encode())
        runner = self.commit('Reviewed runner')
        checked = review._product_digest(self.repo, runner, review._JOURNAL_PRODUCT_PATHS)
        for path in review._SUCCESSOR_REVIEW_PATHS:
            self.write(path, b'journal release verifier ' + path.encode())
        candidate = self.commit('Journal successor')

        with (patch.object(review, '_JOURNAL_BASELINE', baseline),
              patch.object(review, '_JOURNAL_REVIEWED_RUNNER', runner),
              patch.object(review, '_JOURNAL_PRODUCT_SHA256', checked)):
            result = review.review_member_release_source(self.repo, baseline, candidate)
            self.assertEqual(result['schema'], review.JOURNAL_REVIEW_SCHEMA)
            self.assertEqual(result['member_audience'], 'role_only')
            self.assertEqual(result['reviewed_runner_commit'], runner)
            self.assertTrue(result['owner_only_gate_preserved'])
            with self.assertRaisesRegex(ValueError, 'runner or release scope'):
                review.review_member_release_source(self.repo, baseline, runner)
            path = sorted(review._JOURNAL_PRODUCT_PATHS)[0]
            self.write(path, b'changed after review')
            self.git('add', '--', path)
            self.git('commit', '--amend', '--no-edit')
            with self.assertRaisesRegex(ValueError, 'reviewed runner bytes'):
                review.review_member_release_source(self.repo, baseline, self.git('rev-parse', 'HEAD'))
            self.write(review.ENTRY, b'unreviewed owner authorization')
            self.git('add', '--', review.ENTRY)
            self.git('commit', '--amend', '--no-edit')
            with self.assertRaisesRegex(ValueError, 'authorization'):
                review.review_member_release_source(self.repo, baseline, self.git('rev-parse', 'HEAD'))

    def test_fundamental_popup_successor_pins_only_reviewed_frontend_and_test_bytes(self):
        self.config["vars"]["CLOUD_MEMBER_AUDIENCE"] = "role_only"
        original_config = json.dumps(self.config).encode()
        self.write(review.CONFIG, original_config)
        unrelated = "weak_early_beta/new_a/pipeline.py"
        self.write(unrelated, b"frozen daily pipeline")
        paths = review._FUNDAMENTAL_POPUP_REVIEWED_PATHS | review._SUCCESSOR_REVIEW_PATHS
        for path in paths:
            self.write(path, b"predecessor " + path.encode())
        baseline = self.commit("Accepted journal successor")
        for path in paths:
            self.write(path, b"reviewed popup successor " + path.encode())
        candidate = self.commit("Exact popup successor")
        checked = review._product_digest(self.repo, candidate, review._FUNDAMENTAL_POPUP_REVIEWED_PATHS)
        cases = (
            (review.PRESENTATION, b"changed popup after review", "reviewed frontend or test bytes"),
            ("tests/new_a_analytics_presets.test.cjs", b"changed checks", "reviewed frontend or test bytes"),
            (unrelated, b"unexpected change", "reviewed frontend or test scope"),
            (review.CONFIG, original_config.replace(b'"role_only"', b'"tiered"'), "Worker configuration"),
            (review.ENTRY, b"unexpected owner authorization", "authorization"),
        )
        with (patch.object(review, "_FUNDAMENTAL_POPUP_BASELINE", baseline),
              patch.object(review, "_FUNDAMENTAL_POPUP_REVIEWED_SHA256", checked)):
            result = review.review_member_release_source(self.repo, baseline, candidate)
            self.assertEqual(result["schema"], review.FUNDAMENTAL_POPUP_REVIEW_SCHEMA)
            self.assertEqual(result["member_audience"], "role_only")
            self.assertTrue(result["owner_only_gate_preserved"])
            for path, replacement, reason in cases:
                with self.subTest(path=path):
                    self.git("reset", "--hard", candidate)
                    self.write(path, replacement)
                    changed = self.commit("Unreviewed successor")
                    with self.assertRaisesRegex(ValueError, reason):
                        review.review_member_release_source(self.repo, baseline, changed)

    def test_fundamental_impact_successor_pins_colors_and_preserves_access(self):
        self.config["vars"]["CLOUD_MEMBER_AUDIENCE"] = "role_only"
        original_config = json.dumps(self.config).encode()
        self.write(review.CONFIG, original_config)
        role_runtime = "weak-early-beta-gate/src/new-a-member-release.ts"
        self.write(role_runtime, b"exact version-bound role authorization")
        reviewed = review._FUNDAMENTAL_IMPACT_REVIEWED_PATHS
        paths = reviewed | review._SUCCESSOR_REVIEW_PATHS
        for path in paths:
            self.write(path, b"predecessor " + path.encode())
        baseline = self.commit("Accepted fundamental popup")
        for path in paths:
            self.write(path, b"reviewed fundamental impact presentation " + path.encode())
        candidate = self.commit("Exact fundamental impact successor")
        checked = review._product_digest(self.repo, candidate, reviewed)
        cases = (
            (review.PRESENTATION, b"changed color classifier", "reviewed frontend or test bytes"),
            ("tests/new_a_dashboard_details.test.cjs", b"changed checks", "reviewed frontend or test bytes"),
            (role_runtime, b"changed version-bound role authorization", "reviewed frontend or test scope"),
            (review.CONFIG, original_config.replace(b'"role_only"', b'"tiered"'), "Worker configuration"),
            (review.ENTRY, b"changed owner authorization", "authorization"),
        )
        with (patch.object(review, "_FUNDAMENTAL_IMPACT_BASELINE", baseline),
              patch.object(review, "_FUNDAMENTAL_IMPACT_REVIEWED_SHA256", checked)):
            result = review.review_member_release_source(self.repo, baseline, candidate)
            self.assertEqual(result["schema"], review.FUNDAMENTAL_IMPACT_REVIEW_SCHEMA)
            self.assertEqual(result["member_audience"], "role_only")
            self.assertTrue(result["owner_only_gate_preserved"])
            for path, replacement, reason in cases:
                with self.subTest(path=path):
                    self.git("reset", "--hard", candidate)
                    self.write(path, replacement)
                    changed = self.commit("Unreviewed fundamental impact successor")
                    with self.assertRaisesRegex(ValueError, reason):
                        review.review_member_release_source(self.repo, baseline, changed)

    def test_cloud_ui_successor_pins_new_assets_and_keeps_role_only(self):
        self.config["vars"]["CLOUD_MEMBER_AUDIENCE"] = "role_only"
        self.write(review.CONFIG, json.dumps(self.config).encode())
        reviewed = review._CLOUD_UI_PRODUCT_PATHS
        additions = review._CLOUD_UI_ADDITIONS
        paths = reviewed | review._SUCCESSOR_REVIEW_PATHS
        self.assertTrue(additions and additions < reviewed)
        for path in paths - additions:
            self.write(path, b"predecessor " + path.encode())
        baseline = self.commit("Accepted Cloud UI predecessor")
        for path in paths:
            self.write(path, b"reviewed Cloud UI " + path.encode())
        candidate = self.commit("Reviewed Cloud UI and local regression checks")
        checked = review._product_digest(self.repo, candidate, reviewed)
        with (patch.object(review, "_CLOUD_UI_BASELINE", baseline),
              patch.object(review, "_CLOUD_UI_PRODUCT_SHA256", checked)):
            result = review.review_member_release_source(self.repo, baseline, candidate)
            self.assertEqual(result["schema"], review.CLOUD_UI_REVIEW_SCHEMA)
            self.assertEqual(result["member_audience"], "role_only")
            self.assertTrue(result["owner_only_gate_preserved"])
            for path, error in ((min(additions), "reviewed frontend or test bytes"),
                                ("unreviewed-asset.js", "mode or inventory"),
                                (review.ENTRY, "authorization")):
                with self.subTest(path=path):
                    self.git("reset", "--hard", candidate)
                    self.write(path, b"unreviewed change")
                    changed = self.commit("Unreviewed successor")
                    with self.assertRaisesRegex(ValueError, error):
                        review.review_member_release_source(self.repo, baseline, changed)
