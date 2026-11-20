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
from weak_early_beta.new_a.member_release_source_review import (
    COMPLETED_TIMING_REVIEW_SCHEMA, FUNDAMENTAL_IMPACT_REVIEW_SCHEMA, FUNDAMENTAL_POPUP_REVIEW_SCHEMA,
    FUNDAMENTAL_REVIEW_SCHEMA, JOURNAL_REVIEW_SCHEMA, MEMBER_BINDING, PRESENTATION_REVIEW_SCHEMA,
    ROLE_ONLY_REVIEW_SCHEMA,
)


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

        self.source_reviews = {}
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


    def prepare_successor(self, schema=PRESENTATION_REVIEW_SCHEMA):
        prior_result = self.apply(self.issue())
        legacy_review = copy.deepcopy(self.source_review)
        self.source_reviews[legacy_review['accepted_owner_source'], legacy_review['candidate_source']] = legacy_review
        prior = transition.ordinary_runtime_release(self.repo)
        prior_acceptance = read(self.root / 'activation.json')['owner_acceptance']['continuing_acceptance']
        prior_audit = ca.root(self.repo) / 'applications' / Path(prior_result['grant']['path']).stem / 'member-ordinary.json'
        self.operating, self.original = self.repo, self.root / 'activation.json'
        self.before = self.original.read_bytes()
        temp = tempfile.TemporaryDirectory(prefix='new-a-member-ordinary-successor-')
        self.addCleanup(temp.cleanup)
        self.repo = Path(temp.name) / 'repo'
        self.git(self.operating, 'clone', '-q', '--no-hardlinks', str(self.operating), str(self.repo))
        self.root = private_root(self.repo)
        shutil.copytree(private_root(self.operating), self.root)
        self.runtime = self.root.parent / 'daily_runtime'
        self.runtime.mkdir()
        atomic_write(self.runtime.parent / 'daily-runner.config.json', {
            'repoPath': str(self.repo), 'runtimeDir': str(self.runtime),
        })
        self.git(self.repo, 'commit', '--allow-empty', '-qm', 'Successor presentation fixture')
        self.old_source, self.source = prior['source_commit'], ca.head(self.repo)
        self.now += datetime.timedelta(minutes=1)
        self.observed = (self.now - datetime.timedelta(seconds=5)).isoformat()
        self.deployed = (self.now - datetime.timedelta(seconds=15)).isoformat()
        step = self.ci['run_id'] + 1
        self.version = f'00000000-0000-4000-8000-{step:012d}'
        self.deployment_id = f'00000000-0000-4000-9000-{step:012d}'
        self.ci.update(source_commit=self.source, version_id=self.version, build_input_sha256=digest(step), run_id=step)
        self.deployment.update(source_commit=self.source, version_id=self.version, deployment_id=self.deployment_id,
                               observed_at=self.observed, deployed_at=self.deployed, policy_sha256=prior['policy_sha256'],
                               build_input_sha256=self.ci['build_input_sha256'], ci_run_id=self.ci['run_id'])
        self.policy.update(source_commit=self.source, worker_version_id=self.version, observed_at=self.observed)
        self.auth_hashes = {name: file_sha(self.repo / name) for name in ca.AUTH_FILES}
        for kind in ca.PATHS:
            self.measurements[kind].update(source_commit=self.source, auth_source_hashes=self.auth_hashes,
                                           observed_at=self.observed, deployment_version_id=self.version)
            self.raw[kind].update(source_commit=self.source, version_id=self.version,
                                  observed_at=self.observed, deployment_id=self.deployment_id)
        self.source_review = {**legacy_review, 'schema': schema,
                              'accepted_owner_source': self.old_source, 'candidate_source': self.source,
                              'reviewed_diff_sha256': digest([self.old_source, self.source])}
        if schema in member.VERSION_BOUND_HANDOVERS | {ROLE_ONLY_REVIEW_SCHEMA}:
            self.source_review['member_audience'] = 'role_only'
        if schema in member.VERSION_BOUND_HANDOVERS:
            previous_deployment = read(prior_audit)['deployment']
            incumbent = dict(mode='enabled', revision=2, source_commit=prior['source_commit'],
                             worker_version_id=prior['version_id'])
            self.plan['predecessor_member_policy'] = dict(
                self.policy, schema=member.INCUMBENT_POLICY_SCHEMA, source_commit=prior['source_commit'],
                worker_version_id=prior['version_id'], deployment_id=previous_deployment['deployment_id'],
                policy=incumbent, observed_at=(self.now - datetime.timedelta(seconds=30)).isoformat(),
                raw_receipt_sha256='a' * 64,
            )
            self.policy.update(schema=member.EFFECTIVE_OFF_POLICY_SCHEMA, policy=dict(incumbent),
                               deployment_id=self.deployment_id)
            if schema == JOURNAL_REVIEW_SCHEMA:
                self.ci['build_input_sha256'] = self.deployment['build_input_sha256'] = prior['build_input_sha256']
        self.source_reviews[self.old_source, self.source] = self.source_review
        patcher = patch.object(member, 'review_member_release_source',
                               lambda _repo, before, after: copy.deepcopy(self.source_reviews[before, after]))
        patcher.start()
        self.addCleanup(patcher.stop)
        _, self.old = ca.load_reference(self.operating, prior_acceptance, 'records')
        self.plan.update(source_commit=self.source, expected_activation_sha256=file_sha(self.original),
                         prior_acceptance=prior_acceptance, auth_source_hashes=self.auth_hashes,
                         source_review=copy.deepcopy(self.source_review),
                         measurements={kind: dict(id=kind, sha256=digest(value)) for kind, value in self.measurements.items()})
        self.ordinary_review.update(source_commit=self.source)
        self.role_review = {**self.ordinary_review, 'decision': member.DECISION, **member._review(
            self.plan, self.old, self.source_review, {key: self.deployment[key] for key in member.DEPLOYMENT_KEYS},
            self.policy['policy'], None)}
        return prior, prior_audit

    def test_presentation_successor_preserves_policy_and_verifies_prior_member_audit(self):
        prior, prior_audit = self.prepare_successor()
        archived_bytes = prior_audit.read_bytes()
        with self.assertRaisesRegex(ValueError, 'approved live owner policy'):
            member.prepare(self.operating, self.repo, self.plan, **self.readers(
                deployment_reader=lambda: {**self.deployment, 'policy_sha256': 'f' * 64}))
        other = 'other-owner'
        plan = {**self.plan, 'owner_message': {**self.plan['owner_message'], 'author_id': other}}
        primary = {**self.primary, 'message': {**self.primary['message'], 'author_id': other}}
        authority = {**self.prior.owner.authority, 'author_id': other}
        with self.assertRaisesRegex(ValueError, 'change the owner account'):
            member.prepare(self.operating, self.repo, plan, **self.readers(
                primary_reader=lambda _: primary, authority=authority))
        result = self.apply(self.issue())
        self.assertEqual(prior, transition.ordinary_runtime_release(self.operating))
        self.assertEqual(archived_bytes, prior_audit.read_bytes())
        self.assertEqual(transition.ordinary_runtime_release(self.repo)['activation_sha256'], result['after_sha256'])
        archived_copy = self.repo / prior_audit.relative_to(self.operating)
        self.assertEqual(archived_copy.read_bytes(), archived_bytes)
        archived_copy.write_bytes(archived_bytes + b'\n')
        with self.assertRaisesRegex(ValueError, 'completed member ordinary audit'):
            transition.ordinary_runtime_release(self.repo)


    def test_completed_timing_successor_verifies_both_member_predecessors(self):
        _, older_audit = self.prepare_successor()
        older_repo = self.operating
        prior, prior_audit = self.prepare_successor(COMPLETED_TIMING_REVIEW_SCHEMA)
        snapshot = prior_audit.read_bytes()
        with self.assertRaisesRegex(ValueError, 'approved live owner policy'):
            member.prepare(self.operating, self.repo, self.plan, **self.readers(
                deployment_reader=lambda: {**self.deployment, 'policy_sha256': 'f' * 64}))
        result = self.apply(self.issue())
        self.assertEqual(prior, transition.ordinary_runtime_release(self.operating))
        self.assertEqual(snapshot, prior_audit.read_bytes())
        live = transition.ordinary_runtime_release(self.repo)
        self.assertEqual(live['activation_sha256'], result['after_sha256'])
        self.assertEqual(live['source_commit'], self.source)

        archived_older = self.repo / older_audit.relative_to(older_repo)
        archived_older.write_bytes(archived_older.read_bytes() + b'\n')
        with self.assertRaisesRegex(ValueError, 'completed member ordinary audit'):
            transition.ordinary_runtime_release(self.repo)


    def test_fundamental_successor_keeps_the_full_previous_approval_chain(self):
        _, initial_audit = self.prepare_successor()
        initial_repo = self.operating
        self.prepare_successor(COMPLETED_TIMING_REVIEW_SCHEMA)
        previous, timing_audit = self.prepare_successor(FUNDAMENTAL_REVIEW_SCHEMA)
        timing_bytes = timing_audit.read_bytes()
        with self.assertRaisesRegex(ValueError, 'approved live owner policy'):
            member.prepare(self.operating, self.repo, self.plan, **self.readers(
                deployment_reader=lambda: {**self.deployment, 'policy_sha256': 'f' * 64}))
        result = self.apply(self.issue())
        self.assertEqual(transition.ordinary_runtime_release(self.operating), previous)
        self.assertEqual(timing_audit.read_bytes(), timing_bytes)
        self.assertEqual(transition.ordinary_runtime_release(self.repo)['activation_sha256'], result['after_sha256'])
        initial_copy = self.repo / initial_audit.relative_to(initial_repo)
        initial_copy.write_bytes(initial_copy.read_bytes() + b'\n')
        with self.assertRaisesRegex(ValueError, 'completed member ordinary audit'):
            transition.ordinary_runtime_release(self.repo)


    def test_role_only_successor_preserves_ordinary_admission_and_policy(self):
        self.prepare_successor()
        self.prepare_successor(COMPLETED_TIMING_REVIEW_SCHEMA)
        self.prepare_successor(FUNDAMENTAL_REVIEW_SCHEMA)
        prior, prior_audit = self.prepare_successor(ROLE_ONLY_REVIEW_SCHEMA)
        original = prior_audit.read_bytes()
        with self.assertRaisesRegex(ValueError, "role review does not bind"):
            member.prepare(self.operating, self.repo, self.plan, **self.readers(
                role_decision_reader=lambda _: {**self.role_review, "member_audience": "tiered"}))
        with self.assertRaisesRegex(ValueError, "approved live owner policy"):
            member.prepare(self.operating, self.repo, self.plan, **self.readers(
                deployment_reader=lambda: {**self.deployment, "policy_sha256": "f" * 64}))
        result = self.apply(self.issue())
        self.assertEqual(transition.ordinary_runtime_release(self.operating), prior)
        self.assertEqual(prior_audit.read_bytes(), original)
        self.assertEqual(transition.ordinary_runtime_release(self.repo)["activation_sha256"], result["after_sha256"])

    def test_journal_successor_preserves_pinned_enabled_predecessor_and_replays_acceptance(self):
        for schema in (PRESENTATION_REVIEW_SCHEMA, COMPLETED_TIMING_REVIEW_SCHEMA,
                       FUNDAMENTAL_REVIEW_SCHEMA, ROLE_ONLY_REVIEW_SCHEMA):
            self.prepare_successor(schema)
        previous, previous_audit = self.prepare_successor(JOURNAL_REVIEW_SCHEMA)
        incumbent = read(previous_audit)['deployment']
        handover = self.plan['predecessor_member_policy']
        self.assertEqual(member._effective_off(self.policy, MEMBER_BINDING['database_id'], self.deployment,
                                               (incumbent, handover)), handover['policy'])
        for changed in ({'policy': {**self.policy['policy'], 'revision': 3}}, {'primary': False},
                        {'deployment_id': incumbent['deployment_id']}, {'schema': member.INCUMBENT_POLICY_SCHEMA}):
            with self.subTest(changed=changed), self.assertRaisesRegex(ValueError, 'member policy|effective-OFF'):
                member._effective_off(dict(self.policy, **changed), MEMBER_BINDING['database_id'],
                                      self.deployment, (incumbent, handover))
        for changed in ({'version_id': incumbent['version_id']}, {'build_input_sha256': 'a' * 64}):
            policy = dict(self.policy, worker_version_id=changed.get('version_id', self.version))
            with self.subTest(changed=changed), self.assertRaisesRegex(ValueError, 'successor deployment'):
                member._effective_off(policy, MEMBER_BINDING['database_id'],
                                      dict(self.deployment, **changed), (incumbent, handover))
        result = self.apply(self.issue())
        self.assertEqual(transition.ordinary_runtime_release(self.operating), previous)
        self.assertEqual(self.policy['policy'], handover['policy'])
        self.assertEqual(transition.ordinary_runtime_release(self.repo)['activation_sha256'], result['after_sha256'])

    def test_fundamental_popup_successor_binds_new_assets_to_the_existing_exact_role_policy(self):
        schema = FUNDAMENTAL_POPUP_REVIEW_SCHEMA
        self.assertEqual(member.MEMBER_SUCCESSORS[JOURNAL_REVIEW_SCHEMA], schema)
        previous = dict(self.deployment, source_commit=self.old_source,
                        version_id='00000000-0000-4000-8000-000000000208',
                        deployment_id='00000000-0000-4000-9000-000000000208',
                        build_input_sha256='a' * 64,
                        deployed_at=(self.now - datetime.timedelta(minutes=2)).isoformat())
        row = dict(mode='enabled', revision=2, source_commit=self.old_source, worker_version_id=previous['version_id'])
        common = {**self.policy, 'policy': row}
        incumbent = dict(common, schema=member.INCUMBENT_POLICY_SCHEMA, source_commit=self.old_source,
                         worker_version_id=previous['version_id'], deployment_id=previous['deployment_id'],
                         observed_at=(self.now - datetime.timedelta(seconds=30)).isoformat())
        effective_off = dict(common, schema=member.EFFECTIVE_OFF_POLICY_SCHEMA, deployment_id=self.deployment_id)
        handover = previous, incumbent

        def observe(ci, deployment, policy, *, live=True):
            return member._normal_evidence(
                self.source, self.plan['target'], MEMBER_BINDING['database_id'], ci, deployment, policy, self.now,
                live=live, handover=handover, source_review_schema=schema)

        deployment, accepted_policy = observe(self.ci, self.deployment, effective_off)
        self.assertEqual(accepted_policy, row)
        self.assertEqual(observe(self.ci, self.deployment, effective_off, live=False), (deployment, row))
        source_review = {**self.source_review, 'schema': schema, 'member_audience': 'role_only'}
        member._check_successor_policy(source_review, previous, deployment)
        review = member._review({**self.plan, 'predecessor_member_policy': incumbent}, self.old,
                                source_review, deployment, row, None)
        self.assertEqual(review['member_audience'], 'role_only')
        self.assertEqual(review['predecessor_member_policy_sha256'], digest(incumbent))
        old_build = previous['build_input_sha256']
        with self.assertRaisesRegex(ValueError, 'exact normal CI'):
            observe(self.ci, dict(self.deployment, build_input_sha256=old_build), effective_off)
        with self.assertRaisesRegex(ValueError, 'successor deployment'):
            observe(dict(self.ci, build_input_sha256=old_build),
                    dict(self.deployment, build_input_sha256=old_build), effective_off)
        with self.assertRaisesRegex(ValueError, 'approved live owner policy'):
            member._check_successor_policy(source_review, previous, dict(deployment, policy_sha256='f' * 64))
        with self.assertRaisesRegex(ValueError, 'pinned enabled predecessor'):
            observe(self.ci, self.deployment, dict(effective_off, policy=dict(row, revision=3)))

    def test_fundamental_impact_successor_preserves_the_accepted_popup_and_access_policy(self):
        for schema in (PRESENTATION_REVIEW_SCHEMA, COMPLETED_TIMING_REVIEW_SCHEMA, FUNDAMENTAL_REVIEW_SCHEMA,
                       ROLE_ONLY_REVIEW_SCHEMA, JOURNAL_REVIEW_SCHEMA, FUNDAMENTAL_POPUP_REVIEW_SCHEMA):
            self.prepare_successor(schema)
        previous, popup_audit = self.prepare_successor(FUNDAMENTAL_IMPACT_REVIEW_SCHEMA)
        popup_bytes = popup_audit.read_bytes()
        with self.assertRaisesRegex(ValueError, 'pinned enabled predecessor'):
            member.prepare(self.operating, self.repo, self.plan, **self.readers(
                member_policy_reader=lambda: {**self.policy, 'policy': {**self.policy['policy'], 'revision': 3}}))
        with self.assertRaisesRegex(ValueError, 'approved live owner policy'):
            member.prepare(self.operating, self.repo, self.plan, **self.readers(
                deployment_reader=lambda: {**self.deployment, 'policy_sha256': 'f' * 64}))
        result = self.apply(self.issue())
        self.assertEqual(transition.ordinary_runtime_release(self.operating), previous)
        self.assertEqual(popup_audit.read_bytes(), popup_bytes)
        live = transition.ordinary_runtime_release(self.repo)
        self.assertEqual(live['activation_sha256'], result['after_sha256'])
        self.assertEqual(live['policy_sha256'], previous['policy_sha256'])
        self.assertNotEqual(live['build_input_sha256'], previous['build_input_sha256'])
