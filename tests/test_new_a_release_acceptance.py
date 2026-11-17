"""Synthetic host readers and temporary directories ONLY; never real evidence.

Exercise the real continuing acceptance issuance/application/audit chain. Test
fixtures stand in for trusted host observations; they are not production proofs.
"""
import copy
import datetime
import shutil
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from tests import test_new_a_continuing_acceptance as fixtures
from weak_early_beta.new_a import continuing_acceptance as ca
from weak_early_beta.new_a import release_acceptance as handoff
from weak_early_beta.new_a.acceptance import validate_activation
from weak_early_beta.new_a.files import digest, file_sha, private_root, read


class ReleaseAcceptance(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.ContinuingAcceptance()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.operating = self.f.repo
        self.f.apply(self.f.issue())
        self.original = self.tree(self.operating)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.candidate = Path(self.tmp.name) / 'candidate'
        shutil.copytree(self.operating, self.candidate)
        self.old, self.new = self.f.source, 'd' * 40
        self.sources = {self.operating.resolve(): self.old, self.candidate.resolve(): self.new}
        p = patch.object(ca, 'head', lambda repo: self.sources[Path(repo).resolve()])
        p.start(); self.addCleanup(p.stop)
        self.version = '00000000-0000-4000-8000-000000000010'
        self.plan = copy.deepcopy(self.f.plan)
        self.plan.update(source_commit=self.new,
                         expected_activation_sha256=file_sha(private_root(self.operating) / 'activation.json'))
        self.measurements = copy.deepcopy(self.f.measurements)
        self.raw = {}
        for kind, value in self.measurements.items():
            value.update(source_commit=self.new, deployment_version_id=self.version)
            self.raw[kind] = dict(receipt_sha256=value['raw_receipt_sha256'],
                                 source_commit=self.new, target=self.f.target,
                                 version_id=self.version, observed_at=value['observed_at'],
                                 synthetic=False)
        self.raw['owner'].update(owner_identity_verified=True,
                                source_kind='EXISTING_LEGITIMATE_OWNER_SESSION',
                                document=dict(path='/weak_early_beta_latest.html', status=200),
                                api=dict(path='/api/cloud/new-a-finite/access', status=200,
                                         body=dict(authorized=True, strategy='A_BASE')))
        self.rebind()
        self.review = copy.deepcopy(self.f.review)
        self.review['source_commit'] = self.new
        self.deployment = dict(schema='NEW_A_HOST_VERIFIED_DEPLOYMENT_V1',
                               source_commit=self.new, target=self.f.target,
                               version_id=self.version, deployment_succeeded=True,
                               deployed_at='2026-11-16T11:20:00Z',
                               observed_at='2026-11-16T11:25:00Z',
                               raw_receipt_sha256='a' * 64, synthetic=False,
                               platform_signature_claimed=False)

    @staticmethod
    def tree(folder):
        return {str(p.relative_to(folder)): file_sha(p) for p in folder.rglob('*') if p.is_file()}

    def rebind(self):
        self.plan['measurements'] = {k: dict(id=k, sha256=digest(v)) for k, v in self.measurements.items()}

    def ready(self):
        return dict(ok=True, head=self.new, repository=str(self.candidate))

    def prepare(self, **overrides):
        args = dict(primary_reader=lambda _: copy.deepcopy(self.f.primary),
                    measurement_reader=lambda kind: copy.deepcopy(self.measurements[kind]),
                    raw_reader=lambda kind: copy.deepcopy(self.raw[kind]),
                    deployment_reader=lambda: copy.deepcopy(self.deployment),
                    decision_reader=lambda _: copy.deepcopy(self.review),
                    authority=self.f.authority, preflight=self.ready)
        args.update(overrides)
        return handoff.prepare(self.operating, self.candidate, self.plan, **args)

    def assert_old_operates(self):
        self.assertEqual(self.tree(self.operating), self.original)
        validate_activation(read(private_root(self.operating) / 'activation.json'), self.operating)

    def reject(self, reason=None, **overrides):
        old_candidate = self.tree(self.candidate)
        with self.assertRaises((ValueError, KeyError, FileNotFoundError)) as raised:
            self.prepare(dry_run=False, **overrides)
        if reason:
            self.assertIn(reason, str(raised.exception))
        self.assertEqual(self.tree(self.candidate), old_candidate)
        self.assert_old_operates()

    def test_default_dry_run_changes_neither_directory(self):
        before = self.tree(self.candidate)
        value = self.prepare()
        self.assertTrue(value['dry_run'])
        self.assertFalse(value['candidate_acceptance_written'])
        self.assertEqual(self.tree(self.candidate), before)
        self.assert_old_operates()

    def test_fresh_observation_of_same_provider_version_is_allowed(self):
        calls = []
        def fresh():
            value = copy.deepcopy(self.deployment)
            if calls:
                value.update(observed_at='2026-11-16T11:50:00Z', raw_receipt_sha256='b' * 64)
            calls.append(True)
            return value
        value = self.prepare(dry_run=False, deployment_reader=fresh)
        self.assertTrue(handoff.verify_ready(self.operating, self.candidate, value,
                                            deployment_reader=fresh)['ok'])
        self.assert_old_operates()

    def test_only_matching_candidate_gets_real_formal_application(self):
        value = self.prepare(dry_run=False)
        self.assertFalse(value['operationally_promoted'])
        self.assertFalse(value['production_acceptance_written'])
        accepted = read(private_root(self.candidate) / 'activation.json')
        validate_activation(accepted, self.candidate)
        record = ca.validate_record(self.candidate, accepted['owner_acceptance']['continuing_acceptance'])
        self.assertEqual(record['source_commit'], self.new)
        self.assertFalse(record['nonowner_denied'])
        self.assertTrue(handoff.verify_ready(self.operating, self.candidate, value,
                                            deployment_reader=lambda: self.deployment)['ok'])
        self.assert_old_operates()

    def test_old_source_receipt_cannot_be_relabelled(self):
        self.measurements['owner']['source_commit'] = self.old
        self.rebind(); self.reject('version mismatch')

    def test_wrong_target_does_not_update_either_acceptance(self):
        self.plan['target'] = {**self.f.target, 'database_id': 'OTHER'}
        self.reject('protected target')

    def test_changed_auth_sources_are_not_a_code_only_upgrade(self):
        p = self.candidate / next(iter(ca.AUTH_FILES))
        p.write_text('// AUTH CHANGE')
        self.reject('authentication source')

    def test_missing_or_fabricated_raw_receipt_does_not_issue(self):
        self.raw['owner']['receipt_sha256'] = '0' * 64
        self.reject('raw receipt')

    def test_no_synthetic_receipt_is_accepted(self):
        self.raw['owner']['synthetic'] = True
        self.reject('raw receipt')

    def test_missing_owner_response_is_not_inferred_from_a_screenshot(self):
        del self.raw['owner']['api']
        self.reject('normal-response')

    def test_cross_site_403_does_not_prove_owner_200(self):
        self.raw['owner']['api'] = dict(path='/api/cloud/new-a-finite/access', status=403,
                                        body=dict(error='cross_site_request'))
        self.reject('normal-response')

    def test_owner_identity_and_exact_response_body_remain_required(self):
        self.raw['owner']['owner_identity_verified'] = False
        self.reject('normal-response')

    def test_wrong_worker_version_cannot_pass_same_source(self):
        self.raw['owner']['version_id'] = '00000000-0000-4000-8000-000000000011'
        self.reject('raw receipt')

    def test_observation_before_candidate_deployment_is_rejected(self):
        self.deployment['deployed_at'] = '2026-11-16T11:40:00Z'
        self.deployment['observed_at'] = '2026-11-16T11:45:00Z'
        self.reject('raw receipt')

    def test_ci_health_only_cannot_substitute_for_owner_measurement(self):
        self.deployment['schema'] = 'GITHUB_WORKFLOW_SUCCESS_ONLY'
        self.reject('exact deployment')

    def test_existing_opaque_measurement_ids_preserve_formal_reader_contract(self):
        for kind in self.plan['measurements']:
            self.plan['measurements'][kind]['id'] = 'OBSERVATION_' + kind
        value = self.prepare(dry_run=False, measurement_reader=lambda identifier:
                             copy.deepcopy(self.measurements[identifier.removeprefix('OBSERVATION_')]))
        self.assertTrue(value['candidate_acceptance_written'])
        self.assert_old_operates()

    def test_missing_independent_reader_is_rejected(self):
        self.reject('independent measurement', raw_reader=None)

    def test_slack_is_not_relabelled_as_chatgpt_primary(self):
        primary = copy.deepcopy(self.f.primary)
        primary['message']['channel'] = 'slack'
        self.reject('primary message', primary_reader=lambda _: primary)

    def test_expired_management_authority_writes_nothing(self):
        self.plan['management_not_after'] = '2026-11-16T11:59:00Z'
        self.reject('expired')

    def test_preflight_failure_leaves_old_operating_and_retains_attempt(self):
        with self.assertRaisesRegex(ValueError, 'preflight not ready'):
            self.prepare(dry_run=False, preflight=lambda: dict(ok=False))
        self.assert_old_operates()
        root = private_root(self.candidate) / 'release-handoffs'
        self.assertEqual(len(list(root.glob('*/started.json'))), 1)
        self.assertFalse(list(root.glob('*/ready.json')))
        with self.assertRaises(FileExistsError):
            self.prepare(dry_run=False)
        self.assert_old_operates()

    def test_interrupted_application_never_promotes_candidate(self):
        original = ca.atomic_write
        def interrupted(path, value):
            if Path(path).name == 'completed.json':
                raise OSError('SYNTHETIC_DISK_FAILURE')
            original(path, value)
        with patch.object(ca, 'atomic_write', side_effect=interrupted):
            with self.assertRaisesRegex(OSError, 'DISK_FAILURE'):
                self.prepare(dry_run=False)
        self.assert_old_operates()
        self.assertFalse(list((private_root(self.candidate) / 'release-handoffs').glob('*/ready.json')))
        with self.assertRaisesRegex(ValueError, 'baseline copy differs'):
            self.prepare(dry_run=False)

    def test_concurrent_preparation_is_excluded_by_observed_barrier(self):
        entered, release = threading.Event(), threading.Event()
        def blocked():
            entered.set()
            self.assertTrue(release.wait(10))
            return self.ready()
        with ThreadPoolExecutor(max_workers=1) as pool:
            first = pool.submit(self.prepare, dry_run=False, preflight=blocked)
            self.assertTrue(entered.wait(10))
            try:
                with self.assertRaises(FileExistsError):
                    self.prepare(dry_run=False)
                self.assert_old_operates()
            finally:
                release.set()
            first.result(timeout=10)
        self.assert_old_operates()

    def test_concurrent_other_deployment_prevents_ready_but_preserves_old(self):
        calls = []
        def deployment():
            value = copy.deepcopy(self.deployment)
            if calls:
                value['version_id'] = '00000000-0000-4000-8000-000000000011'
            calls.append(True)
            return value
        with self.assertRaisesRegex(ValueError, 'deployment changed'):
            self.prepare(dry_run=False, deployment_reader=deployment)
        self.assert_old_operates()
        self.assertFalse(list((private_root(self.candidate) / 'release-handoffs').glob('*/ready.json')))

    def test_tampered_ready_summary_is_not_an_authorization(self):
        value = self.prepare(dry_run=False)
        value['measurement_hashes']['owner'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'ready receipt'):
            handoff.verify_ready(self.operating, self.candidate, value,
                                 deployment_reader=lambda: self.deployment)
        self.assert_old_operates()

    def test_expired_ready_receipt_cannot_authorize_promotion(self):
        value = self.prepare(dry_run=False)
        self.f.time += datetime.timedelta(hours=1)
        with self.assertRaisesRegex(ValueError, 'expired'):
            handoff.verify_ready(self.operating, self.candidate, value,
                                 deployment_reader=lambda: self.deployment)
        self.assert_old_operates()

    def test_candidate_edit_after_prepare_is_detected(self):
        value = self.prepare(dry_run=False)
        self.sources[self.candidate.resolve()] = 'e' * 40
        with self.assertRaisesRegex(ValueError, 'candidate changed'):
            handoff.verify_ready(self.operating, self.candidate, value,
                                 deployment_reader=lambda: self.deployment)
        self.assert_old_operates()

    def test_changed_operating_version_invalidates_prepared_handoff(self):
        value = self.prepare(dry_run=False)
        self.sources[self.operating.resolve()] = 'f' * 40
        with self.assertRaisesRegex(ValueError, 'source or target changed'):
            handoff.verify_ready(self.operating, self.candidate, value,
                                 deployment_reader=lambda: self.deployment)
        self.sources[self.operating.resolve()] = self.old
        self.assert_old_operates()

    def test_preexisting_mismatch_is_not_repaired_by_overwriting_hash(self):
        self.sources[self.operating.resolve()] = self.new
        with self.assertRaisesRegex(ValueError, 'source or target changed'):
            self.prepare(dry_run=False)
        self.sources[self.operating.resolve()] = self.old
        self.assert_old_operates()


if __name__ == '__main__':
    unittest.main()
