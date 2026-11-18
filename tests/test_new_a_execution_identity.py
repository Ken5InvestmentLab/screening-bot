"""Temporary Git repositories and synthetic host adapters; never remote actions."""
import copy
import csv
import io
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from weak_early_beta.new_a import continuing_acceptance as ca
from weak_early_beta.new_a import execution_identity as identity
from weak_early_beta.new_a.acceptance import validate_activation
from weak_early_beta.new_a.files import atomic_write, digest, file_sha, read
from tests import test_new_a_continuing_acceptance as fixtures


def csv_bytes(rows):
    output = io.StringIO(newline='')
    csv.writer(output, lineterminator='\n').writerows(rows)
    return output.getvalue().encode()


class StableExecutionIdentity(unittest.TestCase):
    def setUp(self):
        self.fixture = f = fixtures.ContinuingAcceptance()
        f.setUp()
        self.addCleanup(f.doCleanups)
        self.clock = patch.object(identity, 'now', lambda: f.time)
        self.clock.start()
        self.addCleanup(self.clock.stop)
        self.repo = f.repo
        self.command('init', '-q')
        self.command('config', 'user.name', 'Isolated Test')
        self.command('config', 'user.email', 'isolated@example.invalid')
        (self.repo / '.gitignore').write_text('.cache/\n')
        self.csv = self.repo / identity.RECEIPTS
        self.csv.parent.mkdir(parents=True, exist_ok=True)
        self.rows = [['detection_id', 'symbol', 'status', 'price', 'updated_at',
                      'd6_exit_reminder_discord_url', 'd6_exit_reminded_at'],
                     ['a', '1234', 'MONITOR', '100', '2026-11-16T00:00:00Z', '', ''],
                     ['b', '5678', 'MONITOR', '200', '2026-11-16T00:00:00Z', '', '']]
        self.csv.write_bytes(csv_bytes(self.rows))
        self.code = self.repo / 'runtime.py'
        self.code.write_text('# synthetic executable source\n')
        self.commit()
        self.anchor = f.source
        self.worker = dict(schema='NEW_A_HOST_ACTUAL_WORKER_IDENTITY_V1',
                           runtime_source_commit=f.source, deployed_source_commit=f.source,
                           target=f.target, synthetic=False,
                           platform_signature_claimed=False, actual_responding_version_verified=True,
                           artifact_source_verified=True, normal_authorization_preserved=True,
                           version_id='00000000-0000-4000-8000-000000000002',
                           deployment_id='00000000-0000-4000-8000-000000000004',
                           deployed_at='2026-11-16T11:00:00Z',
                           deployment_versions=[dict(version_id='00000000-0000-4000-8000-000000000002', percentage=100)],
                           routing_kind='NORMAL_PRODUCTION_URL_NO_OVERRIDE',
                           artifact_sha256=digest('synthetic artifact'), raw_receipt_sha256=digest('synthetic provider receipt'),
                           observed_at='2026-11-16T11:30:00Z')
        self.deps = dict(schema='NEW_A_HOST_FIXED_DEPENDENCIES_V1', source_commit=f.source,
                         target=f.target, synthetic=False, secret_files_read=False,
                         existing_loader_verified=True, per_run_input_guards_unchanged=True,
                         hashes={name: digest('synthetic ' + name) for name in identity.DEPENDENCIES})
        for row in f.measurements.values():
            row['source_commit'] = f.source
            row['deployment_version_id'] = self.worker['version_id']
        text = 'Synthetic owner explicitly authorizes V2 append-only legacy D6 receipt continuity for the exact reviewed execution identity.'
        f.primary['message']['content']['text'] = text
        f.binding = {**f.binding, 'text_sha256': digest(text)}
        f.plan.update(source_commit=f.source, acceptance_schema=ca.STABLE_SCHEMA,
                      owner_message=f.binding, decision=ca.STABLE_DECISION,
                      measurements={k: dict(id=k, sha256=digest(v)) for k, v in f.measurements.items()})
        f.review = f.review_for(f.binding, ca.STABLE_REVIEW)
        self.raw = {}
        for kind, measured in f.measurements.items():
            self.raw[kind] = dict(source_commit=f.source, target=f.target, synthetic=False,
                                 version_id=self.worker['version_id'], artifact_sha256=self.worker['artifact_sha256'],
                                 receipt_sha256=measured['raw_receipt_sha256'], observed_at=measured['observed_at'])
        self.raw['owner'].update(owner_identity_verified=True, source_kind='EXISTING_LEGITIMATE_OWNER_SESSION',
                                 document=dict(path='/weak_early_beta_latest.html', status=200),
                                 api=dict(path='/api/cloud/new-a-finite/access', status=200,
                                          body=dict(authorized=True, strategy='A_BASE')))
        f.plan['execution_identity'], _ = identity.bind(self.repo, f.source, f.target, **self.readers())
        f.review.update(acceptance_schema=ca.STABLE_SCHEMA,
                        execution_identity_sha256=digest(f.plan['execution_identity']))

    def command(self, *args):
        return subprocess.check_output(['git', '--no-optional-locks', *args], cwd=self.repo,
                                       stderr=subprocess.DEVNULL).decode().strip()

    def commit(self):
        self.command('add', '.')
        self.command('commit', '-q', '-m', 'Synthetic isolated change')
        self.fixture.source = self.command('rev-parse', 'HEAD')
        return self.fixture.source

    def readers(self):
        def deps():
            return {**copy.deepcopy(self.deps), 'source_commit': self.fixture.source}
        def worker():
            return {**copy.deepcopy(self.worker), 'runtime_source_commit': self.fixture.source,
                    'observed_at': self.fixture.time.isoformat()}
        return dict(dependency_reader=deps, worker_reader=worker)

    def issue(self, **overrides):
        f = self.fixture
        options = dict(primary_reader=lambda _: copy.deepcopy(f.primary),
                       measurement_reader=lambda kind: copy.deepcopy(f.measurements[kind]),
                       decision_reader=lambda _: copy.deepcopy(f.review), authority=f.authority,
                       raw_reader=lambda kind: copy.deepcopy(self.raw[kind]), **self.readers())
        options.update(overrides)
        return ca.issue(self.repo, f.plan, **options)

    def apply(self, issued, **overrides):
        options = dict(preflight=self.fixture.ready, **self.readers())
        options.update(overrides)
        return ca.apply(self.repo, issued, **options)

    def validate(self):
        return validate_activation(read(self.fixture.activation), self.repo, **self.readers())

    def receipt(self):
        rows = copy.deepcopy(self.rows)
        rows[1][-3:] = ['2026-11-16T11:55:00Z',
                        'https://discord.com/channels/123456789012345678/234567890123456789/345678901234567890',
                        '2026-11-16T11:55:00Z']
        return rows

    def append_receipt(self):
        self.rows = self.receipt()
        self.csv.write_bytes(csv_bytes(self.rows))
        return self.commit()

    def test_new_schema_requires_fresh_evidence_and_never_writes_without_issue(self):
        before = self.fixture.activation.read_bytes()
        issued = self.issue()
        value = ca.validate_record(self.repo, issued['acceptance'], **self.readers())
        self.assertEqual(value['schema'], ca.STABLE_SCHEMA)
        self.assertEqual(self.fixture.activation.read_bytes(), before)
        self.assertEqual(value['source_commit'], self.anchor)

    def test_receipt_only_commit_keeps_current_accepted_execution(self):
        issued = self.issue()
        self.apply(issued)
        immutable = (self.repo / issued['acceptance']['path']).read_bytes()
        self.append_receipt()
        self.validate()
        self.assertEqual((self.repo / issued['acceptance']['path']).read_bytes(), immutable)
        self.assertNotEqual(self.fixture.source, self.anchor)

    def test_v1_still_rejects_receipt_head_change(self):
        del self.fixture.plan['acceptance_schema']
        del self.fixture.plan['execution_identity']
        self.fixture.plan['decision'] = 'CONTINUE_UNTIL_REVOKED_OR_BOUND_SOURCE_CHANGED'
        self.fixture.review = self.fixture.review_for(self.fixture.binding, 'CONTINUING_DAILY_WITH_NONOWNER_UNMEASURED')
        issued = self.fixture.issue()
        self.fixture.apply(issued)
        self.append_receipt()
        with self.assertRaisesRegex(ValueError, 'source or target'):
            self.validate()

    def test_old_record_cannot_be_automatically_promoted(self):
        self.fixture.plan['acceptance_schema'] = ca.SCHEMA
        with self.assertRaisesRegex(ValueError, 'old acceptance'):
            self.issue()

    def test_old_v1_owner_decision_cannot_authorize_v2_meaning(self):
        self.fixture.review = self.fixture.review_for(self.fixture.binding, 'CONTINUING_DAILY_WITH_NONOWNER_UNMEASURED')
        with self.assertRaisesRegex(ValueError, 'intent or scope'):
            self.issue()

    def test_v2_owner_review_requires_exact_schema_and_identity_digest(self):
        for key, value in [('acceptance_schema', ca.SCHEMA), ('execution_identity_sha256', '0' * 64)]:
            previous = copy.deepcopy(self.fixture.review)
            self.fixture.review[key] = value
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'not bound'):
                self.issue()
            self.fixture.review = previous

    def test_v2_missing_host_adapter_never_uses_old_success(self):
        issued = self.issue()
        self.apply(issued)
        with self.assertRaisesRegex(ValueError, 'identity reader unavailable'):
            validate_activation(read(self.fixture.activation), self.repo)

    def test_daily_mutable_state_not_frozen_or_read(self):
        issued = self.issue()
        self.apply(issued)
        folder = self.repo / '.cache/weak_early_beta/new-a-private'
        (folder / 'daily-live.sqlite').write_bytes(b'synthetic daily output changes')
        (folder / 'run-state.json').write_text('{"date":"2026-11-17"}')
        self.validate()
        self.assertNotIn('daily-live.sqlite', str(self.fixture.plan['execution_identity']))

    def test_runtime_code_change_rejects(self):
        issued = self.issue()
        self.apply(issued)
        self.code.write_text('# changed executable\n')
        self.commit()
        with self.assertRaisesRegex(ValueError, 'non-receipt tracked change'):
            self.validate()

    def test_arbitrary_csv_change_rejects(self):
        issued = self.issue()
        self.apply(issued)
        (self.repo / 'prices.csv').write_text('symbol,close\n1234,999\n')
        self.commit()
        with self.assertRaisesRegex(ValueError, 'non-receipt tracked change'):
            self.validate()

    def test_code_changed_then_reverted_still_requires_new_acceptance(self):
        issued = self.issue()
        self.apply(issued)
        before = self.code.read_bytes()
        self.code.write_text('# transient executable change\n')
        self.commit()
        self.code.write_bytes(before)
        self.commit()
        with self.assertRaisesRegex(ValueError, 'non-receipt tracked change'):
            self.validate()

    def test_merge_commit_even_receipt_only_rejected(self):
        issued = self.issue()
        self.apply(issued)
        self.command('checkout', '-q', '-b', 'synthetic-receipt-branch')
        other = self.append_receipt()
        self.command('checkout', '-q', '-b', 'synthetic-main', self.anchor)
        self.command('merge', '-q', '--no-ff', '-m', 'Synthetic receipt merge', other)
        self.fixture.source = self.command('rev-parse', 'HEAD')
        with self.assertRaisesRegex(ValueError, 'merge or discontinuity'):
            self.validate()

    def test_receipt_path_mode_change_rejected(self):
        issued = self.issue()
        self.apply(issued)
        self.csv.write_bytes(csv_bytes(self.receipt()))
        self.command('add', identity.RECEIPTS)
        self.command('update-index', '--chmod=+x', identity.RECEIPTS)
        self.command('commit', '-q', '-m', 'Synthetic mode change')
        self.fixture.source = self.command('rev-parse', 'HEAD')
        with self.assertRaisesRegex(ValueError, 'mode changed'):
            self.validate()

    def test_dirty_or_untracked_executable_rejects(self):
        issued = self.issue()
        self.apply(issued)
        path = self.repo / 'injected.py'
        path.write_text('# untracked\n')
        with self.assertRaisesRegex(ValueError, 'not clean'):
            self.validate()
        path.unlink()
        self.code.write_text('# dirty\n')
        with self.assertRaisesRegex(ValueError, 'not clean'):
            self.validate()

    def test_fixed_dependency_changes_each_reject(self):
        issued = self.issue()
        self.apply(issued)
        for name in identity.DEPENDENCIES:
            original = self.deps['hashes'][name]
            self.deps['hashes'][name] = digest('changed ' + name)
            with self.subTest(dependency=name), self.assertRaisesRegex(ValueError, 'fixed configuration'):
                self.validate()
            self.deps['hashes'][name] = original

    def test_unknown_daily_state_dependency_rejects_contract(self):
        self.deps['hashes']['daily_live_db'] = digest('mutable state')
        with self.assertRaisesRegex(ValueError, 'identities incomplete'):
            self.issue()

    def test_credential_reading_adapter_rejected(self):
        self.deps['secret_files_read'] = True
        with self.assertRaisesRegex(ValueError, 'provenance'):
            self.issue()

    def test_same_auth_and_200_cannot_mask_worker_version_change(self):
        issued = self.issue()
        self.apply(issued)
        self.worker['version_id'] = '00000000-0000-4000-8000-000000000003'
        self.worker['deployment_versions'] = [dict(version_id=self.worker['version_id'], percentage=100)]
        with self.assertRaisesRegex(ValueError, 'Worker version'):
            self.validate()

    def test_same_version_changed_artifact_rejects(self):
        issued = self.issue()
        self.apply(issued)
        self.worker['artifact_sha256'] = digest('different deployed bytes')
        with self.assertRaisesRegex(ValueError, 'deployed artifact'):
            self.validate()

    def test_ignored_override_or_only_declared_version_rejected(self):
        self.worker['actual_responding_version_verified'] = False
        with self.assertRaisesRegex(ValueError, 'not proven'):
            self.issue()

    def test_mixed_deployment_and_override_responses_rejected(self):
        for key, value in [('routing_kind', 'VERSION_OVERRIDE'),
                           ('deployment_versions', [dict(version_id=self.worker['version_id'], percentage=50),
                                                    dict(version_id='00000000-0000-4000-8000-000000000003', percentage=50)])]:
            previous = copy.deepcopy(self.worker)
            self.worker[key] = value
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'not proven'):
                self.issue()
            self.worker = previous

    def test_old_deployment_certificate_is_not_a_new_observation(self):
        reader = lambda: {**self.worker, 'runtime_source_commit': self.fixture.source,
                          'observed_at': '2026-11-16T11:54:00Z'}
        with self.assertRaisesRegex(ValueError, 'stale'):
            self.issue(worker_reader=reader)

    def test_old_source_deployment_cannot_initialize_new_v2(self):
        self.worker['deployed_source_commit'] = 'e' * 40
        with self.assertRaisesRegex(ValueError, 'exact-source deployment'):
            self.issue()

    def test_observation_before_deployment_rejected(self):
        self.worker['deployed_at'] = '2026-11-16T12:01:00Z'
        with self.assertRaisesRegex(ValueError, 'predates deployment'):
            self.issue()

    def test_runtime_reader_mutating_checkout_during_observation_rejected(self):
        issued = self.issue()
        self.apply(issued)
        def changing():
            self.code.write_text('# changed while obtaining observation\n')
            return self.readers()['worker_reader']()
        with self.assertRaisesRegex(ValueError, 'not clean'):
            ca.validate_record(self.repo, issued['acceptance'],
                               dependency_reader=self.readers()['dependency_reader'], worker_reader=changing)

    def test_dependency_changes_between_observations_rejected(self):
        issued = self.issue()
        self.apply(issued)
        count = [0]
        def changing():
            count[0] += 1
            value = self.readers()['dependency_reader']()
            if count[0] > 1:
                value['hashes']['seed'] = digest('changed during observation')
            return value
        with self.assertRaisesRegex(ValueError, 'changed during observation'):
            ca.validate_record(self.repo, issued['acceptance'], dependency_reader=changing,
                               worker_reader=self.readers()['worker_reader'])

    def test_future_and_wrong_d6_receipts_rejected(self):
        before = copy.deepcopy(self.rows)
        after = self.receipt()
        after[1][-3] = after[1][-1] = '2030-11-16T11:55:00Z'
        with self.assertRaisesRegex(ValueError, 'future'):
            identity.receipt_transition(csv_bytes(before), csv_bytes(after))
        for row in before:
            row.append('sixth_xtks_exit_date' if row is before[0] else '2026-11-15')
        after = self.receipt()
        for row in after:
            row.append('sixth_xtks_exit_date' if row is after[0] else '2026-11-15')
        with self.assertRaisesRegex(ValueError, 'D6 date'):
            identity.receipt_transition(csv_bytes(before), csv_bytes(after))

    def test_synthetic_missing_and_wrong_version_measurement_rejected(self):
        for key, value in [('synthetic', True), ('version_id', '00000000-0000-4000-8000-000000000003'),
                           ('artifact_sha256', digest('other')), ('api', dict(path='/access', status=200))]:
            previous = copy.deepcopy(self.raw['owner'])
            self.raw['owner'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.issue()
            self.raw['owner'] = previous

    def test_missing_measurements_and_primary_still_rejected(self):
        with self.assertRaisesRegex(ValueError, 'reader required'):
            self.issue(primary_reader=None)
        with self.assertRaisesRegex(ValueError, 'raw reader unavailable'):
            self.issue(raw_reader=None)

    def test_revoke_still_closes_v2_after_receipt(self):
        issued = self.issue()
        self.apply(issued)
        self.append_receipt()
        self.fixture.plan['source_commit'] = self.anchor
        binding = self.fixture.revocation_binding()
        ca.revoke(self.repo, issued['acceptance'], binding,
                  primary_reader=lambda _: self.fixture.primary,
                  decision_reader=lambda _: self.fixture.review, authority=self.fixture.authority)
        with self.assertRaisesRegex(ValueError, 'revoked'):
            self.validate()

    def test_finite_apply_idempotency_and_expiry_remain(self):
        issued = self.issue()
        first = self.apply(issued)
        second = self.apply(issued)
        self.assertTrue(second['same_operation_replay'])
        self.assertEqual(first['after_sha256'], second['after_sha256'])
        self.fixture.time = self.fixture.time.replace(hour=14)
        with self.assertRaisesRegex(ValueError, 'expired'):
            self.apply(issued)

    def test_concurrent_lock_is_never_overwritten(self):
        issued = self.issue()
        lock = self.repo / '.cache/weak_early_beta/daily_runtime/task-entry.lock'
        lock.parent.mkdir(parents=True, exist_ok=True)
        lock.write_text('OTHER-OPERATION')
        with self.assertRaises(FileExistsError):
            self.apply(issued)
        self.assertEqual(lock.read_text(), 'OTHER-OPERATION')

    def test_missing_completed_application_still_fails(self):
        issued = self.issue()
        self.apply(issued)
        application = Path(issued['application_grant']['path']).stem
        (ca.root(self.repo) / 'applications' / application / 'completed.json').unlink()
        with self.assertRaisesRegex(ValueError, 'audit missing'):
            self.validate()

    def test_changed_activation_or_target_still_fails(self):
        issued = self.issue()
        self.apply(issued)
        current = read(self.fixture.activation)
        current['unrelated_setting'] = 'CHANGED'
        atomic_write(self.fixture.activation, current)
        with self.assertRaisesRegex(ValueError, 'activation changed'):
            self.validate()

    def test_all_invalid_receipt_mutations_reject(self):
        original = csv_bytes(self.rows)
        valid = self.receipt()
        bad = []
        for column, value in [('symbol', '9999'), ('status', 'DONE'), ('price', '123'),
                              ('detection_id', 'other'), ('updated_at', '2026-11-16T11:54:00Z'),
                              ('d6_exit_reminder_discord_url', 'https://example.invalid/x'),
                              ('d6_exit_reminded_at', '2026-11-16T11:55:00')]:
            changed = copy.deepcopy(valid)
            changed[1][changed[0].index(column)] = value
            bad.append(changed)
        bad += [valid + [copy.deepcopy(valid[1])], valid[:-1],
                [valid[0], valid[2], valid[1]],
                [valid[0] + ['unknown'], *[r + ['x'] for r in valid[1:]]]]
        for index, rows in enumerate(bad):
            with self.subTest(case=index), self.assertRaises((ValueError, TypeError)):
                identity.receipt_transition(original, csv_bytes(rows))

    def test_existing_receipt_cannot_be_replaced_or_erased(self):
        before = self.receipt()
        for values in [self.rows[1][-3:], ['2026-11-16T12:00:00Z',
                       'https://discord.com/channels/123456789012345678/234567890123456789/345678901234567899',
                       '2026-11-16T12:00:00Z']]:
            after = copy.deepcopy(before)
            after[1][-3:] = values
            with self.subTest(values=bool(values[1])), self.assertRaisesRegex(ValueError, 'receipt replaced'):
                identity.receipt_transition(csv_bytes(before), csv_bytes(after))


if __name__ == '__main__':
    unittest.main()
