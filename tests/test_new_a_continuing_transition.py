"""Synthetic recovery closure and host evidence; never opens a live session."""
import copy
import datetime
import os
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from tests import test_new_a_continuing_acceptance as fixtures
from weak_early_beta.new_a import continuing_acceptance as acceptance
from weak_early_beta.new_a import continuing_transition as transition
from weak_early_beta.new_a import operational_admission as finite
from weak_early_beta.new_a.acceptance import validate_activation
from weak_early_beta.new_a.files import atomic_write, digest, file_sha, private_root, read


class ContinuingTransitionTests(unittest.TestCase):
    def setUp(self):
        self.owner = fixtures.ContinuingAcceptance()
        self.owner.setUp()
        self.addCleanup(self.owner.doCleanups)
        self.repo = self.owner.repo
        self.git('init', '-q')
        self.git('config', 'core.autocrlf', 'false')
        exclude = self.repo / '.git/info/exclude'
        with exclude.open('a', encoding='utf-8') as file:
            file.write('\n.cache/\n')
        self.git('add', '--', *sorted(acceptance.AUTH_FILES),
                 'weak-early-beta-gate/wrangler.jsonc')
        history_sha = self.commit('Historical approved code')
        self.owner.source = history_sha
        self.owner.plan['source_commit'] = history_sha
        self.owner.review['source_commit'] = history_sha
        for value in self.owner.measurements.values():
            value['source_commit'] = history_sha
        self.owner.plan['measurements'] = self.references(self.owner.measurements)
        self.prior = self.owner.issue()
        self.owner.apply(self.prior)
        old_bytes = self.owner.activation.read_bytes()
        self.runtime = self.repo / '.cache/weak_early_beta/daily_runtime'
        self.config = self.runtime.parent / 'daily-runner.config.json'
        atomic_write(self.config, {'repoPath': str(self.repo), 'runtimeDir': str(self.runtime)})

        # Build a distinct finite recovery revision and then the current revision.
        auth_file = self.repo / 'weak-early-beta-gate/src/index.ts'
        auth_file.write_bytes(b'// finite recovery auth implementation\n')
        self.git('add', '--', str(auth_file.relative_to(self.repo)))
        finite_sha = self.commit('Finite recovery revision')
        finite_record = {
            'schema': finite.SCHEMA,
            'target_date': finite.TARGET,
            'execution_date': finite.EXECUTION,
            'source_commit': finite_sha,
            'target': self.owner.target,
            'strategy': 'A_BASE',
            'issued_at': '2026-11-18T12:00:00+09:00',
            'not_after': '2026-11-18T23:00:00+09:00',
            'scope': 'FINITE_NOV17_NATIVE_ONCE_WITH_PREDEPLOYED_CODE_ONLY_WORKER',
            'historical_acceptance': {
                'source_commit': history_sha,
                'acceptance': self.prior['acceptance'],
                'auth_source_hashes': self.owner.pins,
                'owner_http_observed_at_historical_source': True,
                'current_owner_http_observed': False,
            },
            'original_activation_sha256': file_sha(self.owner.activation),
            'current_auth_source_hashes': self.auth_pins(),
            'owner_http_observed': False,
            'authenticated_nonowner_observed': False,
            'platform_signature_claimed': False,
        }
        self.finite_record = finite_record
        folder = finite.area(self.repo) / digest(finite_record)
        folder.mkdir(parents=True)
        self.finite_backup = folder / 'original-activation.json'
        self.finite_backup.write_bytes(old_bytes)
        record_path = folder / 'record.json'
        atomic_write(record_path, finite_record)
        self.finite_ref = finite.ref(self.repo, record_path)
        overlay = {**self.read_old_activation(), 'operational_admission': self.finite_ref}
        atomic_write(self.owner.activation, overlay)

        auth_file.write_bytes(b'// different reviewed current auth implementation\n')
        self.git('add', '--', str(auth_file.relative_to(self.repo)))
        self.current = self.commit('Current production candidate')
        self.owner.source = self.current
        self.owner.time = datetime.datetime(2026, 11, 19, 8, tzinfo=datetime.timezone.utc)
        self.activation_sha = file_sha(self.owner.activation)
        self.version = '00000000-0000-4000-8000-000000000019'
        self.plan = copy.deepcopy(self.owner.plan)
        current_pins = self.auth_pins()
        self.plan.update(
            source_commit=self.current, expected_activation_sha256=self.activation_sha,
            decision=transition.DECISION,
            auth_source_hashes=current_pins, management_not_after='2026-11-19T08:30:00Z',
            prior_acceptance=self.prior['acceptance'], finite_admission=self.finite_ref,
        )
        self.owner.primary['message']['sent_at'] = '2026-11-19T07:35:00Z'
        self.measurements = copy.deepcopy(self.owner.measurements)
        self.raw = {}
        for kind, value in self.measurements.items():
            value.update(source_commit=self.current, deployment_version_id=self.version,
                         auth_source_hashes=current_pins, observed_at='2026-11-19T07:50:00Z')
            self.raw[kind] = dict(receipt_sha256=value['raw_receipt_sha256'],
                                  source_commit=self.current, target=self.owner.target,
                                  version_id=self.version, observed_at=value['observed_at'],
                                  synthetic=False)
        self.raw['owner'].update(
            owner_identity_verified=True, source_kind='EXISTING_LEGITIMATE_OWNER_SESSION',
            document=dict(path='/weak_early_beta_latest.html', status=200),
            api=dict(path='/api/cloud/new-a-finite/access', status=200,
                     body=dict(authorized=True, strategy='A_BASE')),
        )
        self.plan['measurements'] = self.references(self.measurements)
        self.deployment = dict(
            schema='NEW_A_HOST_VERIFIED_DEPLOYMENT_V1', source_commit=self.current,
            target=self.owner.target, version_id=self.version, deployment_succeeded=True,
            deployed_at='2026-11-19T07:25:00Z', observed_at='2026-11-19T07:30:00Z',
            raw_receipt_sha256='a'*64, synthetic=False, platform_signature_claimed=False,
        )
        receipts = {'terminal_runner': 'b' * 64, 'independent_readback': 'c' * 64}
        self.closure = dict(
            schema='NEW_A_VERIFIED_FINITE_COMPLETION_V1', finite_admission=self.finite_ref,
            source_commit=finite_sha, target_date=finite.TARGET, execution_date=finite.EXECUTION,
            publication_verified=True, notification_reconciled=True,
            receipt_hashes=receipts, completion_sha256=digest(receipts),
        )
        self.review = self.owner.review_for(self.owner.binding, transition.DECISION)
        self.review.update(
            source_commit=self.current, previous_acceptance=self.prior['acceptance'],
            finite_admission=self.finite_ref, expected_activation_sha256=self.activation_sha,
            closure_sha256=digest(self.closure),
            historical_auth_source_hashes=self.owner.pins,
            current_auth_source_hashes=current_pins, existing_access_policy_preserved=True,
            management_not_after=self.plan['management_not_after'],
            deployment_version_id=self.version,
        )

    def read_old_activation(self):
        return read(self.owner.activation)

    def git(self, *args):
        return subprocess.check_output(
            ['git', '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
             '-c', 'commit.gpgsign=false', *args], cwd=self.repo, text=True,
        ).strip()

    def commit(self, message):
        self.git('commit', '-qm', message)
        return self.git('rev-parse', 'HEAD')

    def auth_pins(self):
        return {path: file_sha(self.repo / path) for path in acceptance.AUTH_FILES}

    @staticmethod
    def references(values):
        return {kind: dict(id=kind, sha256=digest(value)) for kind, value in values.items()}

    def readers(self, **overrides):
        readers = dict(
            primary_reader=lambda _: copy.deepcopy(self.owner.primary),
            measurement_reader=lambda kind: copy.deepcopy(self.measurements[kind]),
            raw_reader=lambda kind: copy.deepcopy(self.raw[kind]),
            deployment_reader=lambda: copy.deepcopy(self.deployment),
            decision_reader=lambda _: copy.deepcopy(self.review),
            authority=self.owner.authority,
            closure_reader=lambda *_: copy.deepcopy(self.closure),
        )
        return {**readers, **overrides}

    def prepare(self, **overrides):
        return transition.prepare(self.repo, self.plan, **self.readers(**overrides))

    def ordinary_issue(self):
        plan = {**self.plan, 'decision': 'CONTINUE_UNTIL_REVOKED_OR_BOUND_SOURCE_CHANGED'}
        review = {**self.review, 'decision': 'CONTINUING_DAILY_WITH_NONOWNER_UNMEASURED'}
        return acceptance.issue(
            self.repo, plan,
            primary_reader=lambda _: copy.deepcopy(self.owner.primary),
            measurement_reader=lambda kind: copy.deepcopy(self.measurements[kind]),
            decision_reader=lambda _: copy.deepcopy(review), authority=self.owner.authority,
        )

    def apply(self, issued, *, preflight=None, **overrides):
        return transition.apply(
            self.repo, self.plan, issued,
            preflight=preflight or (lambda: {**self.owner.ready(), 'sideEffects': False}),
            **self.readers(**overrides),
        )

    def bytes_in_private_tree(self):
        root = private_root(self.repo)
        return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}

    def rejects_without_mutation(self, reason, **overrides):
        before = self.bytes_in_private_tree()
        with self.assertRaisesRegex(ValueError, reason):
            self.prepare(**overrides)
        self.assertEqual(self.bytes_in_private_tree(), before)

    def test_completed_finite_history_and_current_observations_prepare_without_writes(self):
        before = self.bytes_in_private_tree()
        result = self.prepare()
        self.assertEqual(self.bytes_in_private_tree(), before)
        self.assertEqual(result['status'], 'prepared-not-applied')
        self.assertEqual(result['source_commit'], self.current)
        self.assertEqual(result['deployment_version_id'], self.version)
        self.assertFalse(result['apply_authorized'])
        self.assertTrue(self.read_old_activation()['operational_admission'])

    def test_old_source_or_old_worker_measurement_is_rejected(self):
        self.raw['owner']['version_id'] = '00000000-0000-4000-8000-000000000018'
        self.rejects_without_mutation('raw receipt source')
        self.raw['owner']['version_id'] = self.version
        self.plan['source_commit'] = self.finite_record['source_commit']
        self.rejects_without_mutation('transition decision, target')

    def test_owner_and_current_normal_api_response_are_required(self):
        self.rejects_without_mutation(
            'host-verified owner authority', authority={**self.owner.authority, 'author_id': 'OTHER'},
        )
        self.raw['owner']['api']['status'] = 403
        self.rejects_without_mutation('owner normal-response')

    def test_expired_authority_or_incomplete_finite_receipt_never_prepares(self):
        self.plan['management_not_after'] = '2026-11-19T07:59:00Z'
        self.rejects_without_mutation('management authority expired')
        self.plan['management_not_after'] = '2026-11-19T08:30:00Z'
        self.closure['notification_reconciled'] = False
        self.review['closure_sha256'] = digest(self.closure)
        self.rejects_without_mutation('terminal recovery proof')

    def test_review_must_bind_exact_activation_and_completion(self):
        original = self.review.copy()
        self.review['closure_sha256'] = 'd' * 64
        self.rejects_without_mutation('review is not bound')
        self.review = original
        self.review['expected_activation_sha256'] = 'e' * 64
        self.rejects_without_mutation('review is not bound')

    def test_changed_live_version_during_preparation_is_rejected(self):
        observations = iter([self.deployment, {
            **self.deployment, 'version_id': '00000000-0000-4000-8000-000000000020',
        }])
        self.rejects_without_mutation(
            'normal deployment changed', deployment_reader=lambda: next(observations),
        )

    def test_tampered_historical_activation_never_prepares(self):
        self.finite_backup.write_bytes(self.finite_backup.read_bytes() + b' ')
        self.rejects_without_mutation('historical activation backup differs')


    def test_opt_in_apply_preserves_history_and_enables_ordinary_validation(self):
        issued = self.ordinary_issue()
        before = self.owner.activation.read_bytes()
        finite_before = self.finite_backup.read_bytes()
        with self.assertRaisesRegex(ValueError, 'authentication source|finite'):
            acceptance.apply(self.repo, issued, preflight=self.owner.ready,
                             previous_acceptance=self.prior['acceptance'])
        self.assertEqual(self.owner.activation.read_bytes(), before)
        self.apply(issued)
        value = read(self.owner.activation)
        self.assertNotIn('operational_admission', value)
        self.assertEqual(value['owner_acceptance']['continuing_acceptance'], issued['acceptance'])
        self.assertEqual(value['unrelated_setting'], 'PRESERVE')
        self.assertEqual(self.finite_backup.read_bytes(), finite_before)
        private = private_root(self.repo)
        self.assertTrue(any(
            file.read_bytes() == before
            for file in (private / 'continuing-acceptance/applications').rglob('original.json')
        ))
        self.assertIs(validate_activation(value, self.repo), value)
        self.assertTrue(self.apply(issued)['same_operation_replay'])
        applied = self.owner.activation.read_bytes()
        self.owner.activation.write_bytes(applied + b' ')
        with self.assertRaisesRegex(ValueError, 'completed transition activation changed'):
            self.apply(issued)
        self.owner.activation.write_bytes(applied)
        old, _ = acceptance.load_reference(self.repo, self.prior['acceptance'], 'records')
        revocation = acceptance.root(self.repo) / 'revocations' / (old.stem + '.json')
        acceptance.immutable(revocation, {'fixture_revocation': True})
        with self.assertRaisesRegex(ValueError, 'revoked'):
            validate_activation(value, self.repo)

    def test_ambiguous_replace_preserves_claim_and_cannot_replay(self):
        issued = self.ordinary_issue()
        before = self.owner.activation.read_bytes()
        with patch.object(transition, 'atomic_write', return_value=None):
            with self.assertRaisesRegex(ValueError, 'readback ambiguous'):
                self.apply(issued)
        with self.assertRaises(FileExistsError):
            self.apply(issued)
        self.assertEqual(self.owner.activation.read_bytes(), before)
        operation = acceptance.root(self.repo) / 'applications' / Path(issued['application_grant']['path']).stem
        self.assertTrue((operation / 'claim.json').is_file())
        self.assertFalse((operation / 'completed.json').exists())

    def test_lost_replace_ack_leaves_runtime_closed_and_does_not_reapply(self):
        issued = self.ordinary_issue()
        real_replace = os.replace
        def replaced_but_no_ack(source, destination):
            real_replace(source, destination)
            if Path(destination) == self.owner.activation:
                raise OSError('fixture lost replace acknowledgement')
        with patch.object(transition.os, 'replace', side_effect=replaced_but_no_ack):
            with self.assertRaisesRegex(OSError, 'fixture lost replace acknowledgement'):
                self.apply(issued)
        value = read(self.owner.activation)
        self.assertNotIn('operational_admission', value)
        with self.assertRaisesRegex(ValueError, 'completed application audit missing'):
            validate_activation(value, self.repo)
        with self.assertRaisesRegex(ValueError, 'activation baseline changed'):
            self.apply(issued)
        self.assertEqual(read(self.owner.activation), value)

    def test_mismatched_config_runtime_never_changes_activation(self):
        issued = self.ordinary_issue()
        before = self.owner.activation.read_bytes()
        mismatched = self.runtime.with_name('unrelated-runtime')
        mismatched.mkdir()
        atomic_write(self.config, {'repoPath': str(self.repo), 'runtimeDir': str(mismatched)})
        with self.assertRaisesRegex(ValueError, 'runtime'):
            self.apply(issued)
        self.assertEqual(self.owner.activation.read_bytes(), before)
        self.assertFalse((mismatched / 'daily.lock').exists())
        self.assertFalse((self.runtime / 'daily.lock').exists())

    def test_apply_cannot_erase_other_runner_lock(self):
        issued = self.ordinary_issue()
        lock = self.runtime / 'daily.lock'
        lock.write_text('OTHER_OWNER', encoding='utf-8')
        before = self.owner.activation.read_bytes()
        with self.assertRaises((FileExistsError, ValueError)):
            self.apply(issued)
        self.assertEqual(lock.read_text(encoding='utf-8'), 'OTHER_OWNER')
        self.assertEqual(self.owner.activation.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
