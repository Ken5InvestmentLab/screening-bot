"""Isolated formal host fixtures. No browser, provider, network or live authority."""
import copy
import datetime
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from tests import test_new_a_continuing_transition as fixtures
from weak_early_beta.new_a import continuing_acceptance as ca
from weak_early_beta.new_a import continuing_transition as transition
from weak_early_beta.new_a import member_ordinary_acceptance as member
from weak_early_beta.new_a.files import atomic_write, digest, file_sha, private_root, read
from weak_early_beta.new_a.member_release_source_review import MEMBER_BINDING


class MemberOrdinaryAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.prior = fixtures.ContinuingTransitionTests()
        self.prior.setUp()
        self.addCleanup(self.prior.doCleanups)
        self.prior.apply(self.prior.ordinary_issue())
        self.operating = self.prior.repo
        self.candidate_temp = tempfile.TemporaryDirectory(prefix='new-a-member-ordinary-candidate-')
        self.addCleanup(self.candidate_temp.cleanup)
        self.repo = Path(self.candidate_temp.name) / 'repo'
        real_head = patch.object(ca, 'head', lambda repo: self.git(repo, 'rev-parse', 'HEAD'))
        real_head.start()
        self.addCleanup(real_head.stop)
        self.git(self.operating, 'clone', '-q', '--no-hardlinks', str(self.operating), str(self.repo))
        with (self.repo / '.git/info/exclude').open('a', encoding='utf-8') as stream:
            stream.write('\n.cache/\n')
        self.root = private_root(self.repo)
        self.runtime = self.repo / '.cache/weak_early_beta/daily_runtime'
        self.runtime.mkdir(parents=True)
        self.original = private_root(self.operating) / 'activation.json'
        self.before = self.original.read_bytes()
        shutil.copytree(private_root(self.operating), self.root)
        atomic_write(self.runtime.parent / 'daily-runner.config.json', {
            'repoPath': str(self.repo), 'runtimeDir': str(self.runtime),
        })

        route = self.repo / 'weak-early-beta-gate/src/index.ts'
        route.write_bytes(b'// distinct reviewed role candidate implementation\n')
        self.git(self.repo, 'add', '--', str(route.relative_to(self.repo)))
        self.git(self.repo, 'commit', '-qm', 'New role-capable source')
        self.old_source = ca.head(self.operating)
        self.source = ca.head(self.repo)
        self.target = ca.target(self.repo)
        self.now = ca.now() + datetime.timedelta(minutes=1)
        patcher = patch.object(ca, 'now', lambda: self.now)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.version = '00000000-0000-4000-8000-000000000035'
        self.deployment_id = '00000000-0000-4000-8000-000000000036'
        self.observed = (self.now - datetime.timedelta(seconds=5)).isoformat()
        self.deployed = (self.now - datetime.timedelta(seconds=15)).isoformat()
        self.baseline = transition.ordinary_runtime_release(self.operating)
        previous = read(self.original)['owner_acceptance']['continuing_acceptance']
        _, self.old = ca.load_reference(self.operating, previous, 'records')

        self.source_review = dict(schema='NEW_A_MEMBER_RELEASE_SOURCE_REVIEW_V1',
                                  accepted_owner_source=self.old_source, candidate_source=self.source,
                                  reviewed_diff_sha256='1' * 64, member_database_id=MEMBER_BINDING['database_id'],
                                  member_support_configured=True, owner_only_gate_preserved=True)
        source_review_patch = patch.object(member, 'review_member_release_source', lambda *_: copy.deepcopy(self.source_review))
        source_review_patch.start()
        self.addCleanup(source_review_patch.stop)
        self.primary = copy.deepcopy(self.prior.owner.primary)
        self.policy = dict(schema='NEW_A_HOST_MEMBER_POLICY_OFF_V1', database_id=MEMBER_BINDING['database_id'],
                           source_commit=self.source, worker_version_id=self.version, primary=True, policy=None,
                           synthetic=False, platform_signature_claimed=False, raw_receipt_sha256='2' * 64,
                           observed_at=self.observed)
        self.ci = dict(schema='NEW_A_NORMAL_CI_DEPLOYMENT_V1', source_commit=self.source,
                       worker=ca.SERVICE, workflow='weak-early-beta-report-deploy.yml', status='completed',
                       conclusion='success', standard_wrangler_deploy=True, version_id=self.version,
                       build_input_sha256='3' * 64, raw_log_sha256='4' * 64, run_id=325,
                       tag='cloud-deploy-member-ordinary-fixture')
        self.deployment = dict(schema='NEW_A_HOST_VERIFIED_DEPLOYMENT_V1', source_commit=self.source,
                               target=self.target, version_id=self.version, deployment_id=self.deployment_id,
                               deployment_succeeded=True, deployed_at=self.deployed, observed_at=self.observed,
                               raw_receipt_sha256='5' * 64, synthetic=False, platform_signature_claimed=False,
                               normal_origin=member.ORIGIN, live_traffic_percent=100, active_owner_sha256='6' * 64,
                               build_input_sha256=self.ci['build_input_sha256'], policy_sha256='7' * 64,
                               ci_run_id=self.ci['run_id'], tag=self.ci['tag'])
        self.measurements = copy.deepcopy(self.prior.measurements)
        self.raw = copy.deepcopy(self.prior.raw)
        self.auth_hashes = {name: file_sha(self.repo / name) for name in ca.AUTH_FILES}
        for kind in ca.PATHS:
            self.measurements[kind].update(source_commit=self.source, auth_source_hashes=self.auth_hashes,
                                           observed_at=self.observed, deployment_version_id=self.version)
            self.raw[kind].update(source_commit=self.source, version_id=self.version, observed_at=self.observed,
                                  origin=member.ORIGIN, deployment_id=self.deployment_id)
        self.measurements['direct']['observations'].append(dict(path=member.ROUTE, status=401, private_gate=True))
        self.plan = {**self.prior.plan, 'source_commit': self.source, 'target': self.target, 'decision': member.DECISION,
                     'expected_activation_sha256': file_sha(self.original), 'prior_acceptance': previous,
                     'auth_source_hashes': self.auth_hashes, 'source_review': copy.deepcopy(self.source_review),
                     'management_not_after': (self.now + datetime.timedelta(minutes=20)).isoformat(),
                     'measurements': {kind: dict(id=kind, sha256=digest(value)) for kind, value in self.measurements.items()}}
        self.plan.pop('finite_admission')
        self.ordinary_review = {**self.prior.owner.review, 'source_commit': self.source, 'decision': member.ORDINARY_DECISION}
        self.role_review = {**self.ordinary_review, 'decision': member.DECISION, **member._review(
            self.plan, self.old, self.source_review, {k: self.deployment[k] for k in member.DEPLOYMENT_KEYS}, None, None)}

    @staticmethod
    def git(repo, *args):
        return subprocess.check_output(['git', '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                                        '-c', 'commit.gpgsign=false', *args], cwd=repo).decode().strip()

    def readers(self, **overrides):
        return dict(
            dict(primary_reader=lambda _: self.primary, ordinary_decision_reader=lambda _: self.ordinary_review,
                 role_decision_reader=lambda _: self.role_review, authority=self.prior.owner.authority,
                 ci_reader=lambda: self.ci, deployment_reader=lambda: self.deployment,
                 member_policy_reader=lambda: self.policy, measurement_reader=self.measurements.__getitem__,
                 raw_reader=self.raw.__getitem__), **overrides,
        )

    def preflight(self):
        return dict(ok=True, sideEffects=False, head=self.source, repository=str(self.repo))

    def issue(self):
        return member.issue(self.operating, self.repo, self.plan, **self.readers())

    def apply(self, issued, **readers):
        return member.apply(self.operating, self.repo, self.plan, issued, preflight=self.preflight,
                            **self.readers(**readers))

    def test_member_ordinary_loads_and_old_approval_stays_byte_exact(self):
        self.assertFalse(member.prepare(self.operating, self.repo, self.plan, **self.readers())['apply_authorized'])
        self.assertEqual((self.root / 'activation.json').read_bytes(), self.before)
        issued = self.issue()
        owner = 'new-a-release:' + '9' * 64
        old_runtime = self.prior.runtime
        old_locks = (old_runtime / 'task-entry.lock', old_runtime / 'daily.lock',
                     old_runtime.parent / 'exit-reminder-runner.lock')
        for lock in old_locks:
            lock.write_text(owner, encoding='utf-8')
        result = self.apply(issued, operating_arbitration_owner=owner)
        self.assertEqual([lock.read_text() for lock in old_locks], [owner] * len(old_locks))
        self.assertEqual(result['schema'], member.APPLICATION_SCHEMA)
        self.assertFalse(result['same_operation_replay'])
        self.assertEqual(self.original.read_bytes(), self.before)
        self.assertEqual(transition.ordinary_runtime_release(self.operating), self.baseline)
        live = transition.ordinary_runtime_release(self.repo)
        self.assertEqual(live['source_commit'], self.source)
        self.assertEqual(live['version_id'], self.version)
        self.assertEqual(live['activation_sha256'], result['after_sha256'])
        self.assertTrue(self.apply(issued)['same_operation_replay'])
        self.assertFalse((self.runtime / 'daily.lock').exists())

    def test_wrong_provider_traffic_role_policy_or_raw_origin_refuses(self):
        for overrides, message in [
            (dict(deployment_reader=lambda: {**self.deployment, 'live_traffic_percent': 99}), 'normal CI'),
            (dict(member_policy_reader=lambda: {**self.policy, 'policy': {'mode': 'canary'}}), 'remain OFF'),
            (dict(raw_reader=lambda kind: {**self.raw[kind], 'origin': 'https://stage.invalid'}), 'normal-origin'),
            (dict(ci_reader=lambda: {**self.ci, 'build_input_sha256': '8' * 64}), 'normal CI'),
        ]:
            with self.subTest(error=message), self.assertRaisesRegex(ValueError, message):
                member.prepare(self.operating, self.repo, self.plan, **self.readers(**overrides))
        self.assertEqual((self.root / 'activation.json').read_bytes(), self.before)

    def test_separate_role_review_binds_replacement_and_old_owner(self):
        altered = {**self.role_review, 'reviewed_diff_sha256': '8' * 64}
        with self.assertRaisesRegex(ValueError, 'role review'):
            member.prepare(self.operating, self.repo, self.plan, **self.readers(role_decision_reader=lambda _: altered))
        authority = {**self.prior.owner.authority, 'author_id': 'different'}
        with self.assertRaisesRegex(ValueError, 'verified owner'):
            member.prepare(self.operating, self.repo, self.plan, **self.readers(authority=authority))
        self.assertEqual((self.root / 'activation.json').read_bytes(), self.before)

    def test_changed_policy_before_replace_preserves_intent_and_old_activation(self):
        issued = self.issue()
        observations = iter((self.policy, {**self.policy, 'policy': {'mode': 'enabled'}}))
        with self.assertRaisesRegex(ValueError, 'remain OFF'):
            self.apply(issued, member_policy_reader=lambda: next(observations))
        self.assertEqual((self.root / 'activation.json').read_bytes(), self.before)
        self.assertEqual(self.original.read_bytes(), self.before)
        self.assertEqual(len(list((ca.root(self.repo) / 'applications').glob('*/member-ordinary.json'))), 1)
        with self.assertRaises(FileExistsError):
            self.apply(issued)

    def test_completed_audit_mutation_cannot_fallback_to_generic_release(self):
        result = self.apply(self.issue())
        folder = ca.root(self.repo) / 'applications' / Path(result['grant']['path']).stem
        audit = folder / 'member-ordinary.json'
        value = read(audit)
        value['deployment']['version_id'] = '00000000-0000-4000-8000-000000000099'
        atomic_write(audit, value)
        with self.assertRaisesRegex(ValueError, 'completed member ordinary audit'):
            transition.ordinary_runtime_release(self.repo)
