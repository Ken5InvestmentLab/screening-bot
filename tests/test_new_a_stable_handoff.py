"""Connect existing APIs using temporary Git and synthetic evidence only.

No successful V2 private-probe promotion is fabricated: its normal-100% proof
and the existing private-pretraffic coordinator are intentionally incompatible.
"""
import copy
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests import test_new_a_execution_identity as fixtures
from weak_early_beta.new_a import continuing_acceptance as ca
from weak_early_beta.new_a import execution_identity as execution
from weak_early_beta.new_a import release_acceptance as handoff
from weak_early_beta.new_a.files import digest, file_sha, private_root, read


class StableHandoff(unittest.TestCase):
    def setUp(self):
        self.f = f = fixtures.StableExecutionIdentity()
        f.setUp()
        self.addCleanup(f.doCleanups)
        f.apply(f.issue())
        self.operating = f.repo
        self.old = f.anchor
        self.anchor_record = read(f.fixture.activation)['owner_acceptance']['continuing_acceptance']
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.candidate = Path(self.tmp.name) / 'candidate'
        shutil.copytree(self.operating, self.candidate)
        (self.candidate / 'runtime.py').write_text('# synthetic next candidate executable\n')
        self.git(self.candidate, 'add', 'runtime.py')
        self.git(self.candidate, 'commit', '-q', '-m', 'Synthetic candidate')
        self.new = self.git(self.candidate, 'rev-parse', 'HEAD')
        self.sources = {self.operating.resolve(): self.old, self.candidate.resolve(): self.new}
        context = patch.object(ca, 'head', lambda repo: self.sources[Path(repo).resolve()])
        context.start()
        self.addCleanup(context.stop)
        self.plan = copy.deepcopy(f.fixture.plan)
        self.plan.update(source_commit=self.new, expected_activation_sha256=file_sha(f.fixture.activation))
        self.measurements = copy.deepcopy(f.fixture.measurements)
        self.raw = copy.deepcopy(f.raw)
        self.version = '00000000-0000-4000-8000-000000000010'
        for kind, value in self.measurements.items():
            value.update(source_commit=self.new, deployment_version_id=self.version)
            self.raw[kind].update(source_commit=self.new, version_id=self.version,
                                  artifact_sha256=digest('synthetic candidate artifact'))
        self.plan['measurements'] = {k: dict(id=k, sha256=digest(v)) for k, v in self.measurements.items()}
        expected = copy.deepcopy(self.plan['execution_identity'])
        expected.update(anchor_source=self.new, tracked=execution.tracked_identity(self.candidate, self.new))
        expected['worker'].update(deployed_source_commit=self.new, version_id=self.version,
                                  deployment_id='00000000-0000-4000-8000-000000000011',
                                  deployment_versions=[dict(version_id=self.version, percentage=100)],
                                  artifact_sha256=digest('synthetic candidate artifact'))
        # This is an unproven requested identity, not an accepted observation.
        self.plan['execution_identity'] = expected
        self.review = copy.deepcopy(f.fixture.review)
        self.review.update(source_commit=self.new, execution_identity_sha256=digest(expected))
        self.deployment = dict(schema='NEW_A_HOST_VERIFIED_PRIVATE_CANDIDATE_PROBE_V1',
                               source_commit=self.new, target=f.fixture.target, version_id=self.version,
                               deployment_succeeded=False, uploaded_only=True, live_traffic_percent=0,
                               normal_protected_probe=True, existing_owner_authorization=True,
                               access_policy_unchanged=True, public_preview=False,
                               version_available_at='2026-11-16T11:00:00Z',
                               observed_at='2026-11-16T11:30:00Z', raw_receipt_sha256=digest('synthetic private probe'),
                               synthetic=False, platform_signature_claimed=False)
        self.original = self.tree(self.operating)
        self.candidate_original = self.tree(self.candidate)
        self.calls = []
        self.candidate_mode = 'PRIVATE_PRETRAFFIC_PROBE'

    @staticmethod
    def git(repo, *args):
        return subprocess.check_output(['git', '--no-optional-locks', *args], cwd=repo,
                                       stderr=subprocess.DEVNULL).decode().strip()

    @staticmethod
    def tree(repo):
        return {str(path.relative_to(repo)): file_sha(path) for path in repo.rglob('*')
                if path.is_file() and '.git' not in path.relative_to(repo).parts}

    def dependency_reader(self, repo):
        self.calls.append(('dependency', Path(repo).resolve()))
        return {**copy.deepcopy(self.f.deps), 'source_commit': self.sources[Path(repo).resolve()]}

    def worker_reader(self, repo):
        repo = Path(repo).resolve()
        self.calls.append(('worker', repo))
        value = {**copy.deepcopy(self.f.worker), 'runtime_source_commit': self.sources[repo],
                 'observed_at': self.f.fixture.time.isoformat()}
        if repo == self.candidate.resolve():
            # Genuine PRIVATE proof remains private. Never report it as normal 100%.
            value.update(deployed_source_commit=self.new, version_id=self.version,
                         deployment_id='00000000-0000-4000-8000-000000000011',
                         deployment_versions=[dict(version_id=self.version, percentage=0 if self.candidate_mode == 'PRIVATE_PRETRAFFIC_PROBE' else 100)],
                         artifact_sha256=digest('synthetic candidate artifact'),
                         routing_kind=self.candidate_mode)
        return value

    def readers(self):
        return dict(dependency_reader=self.dependency_reader, worker_reader=self.worker_reader)

    def prepare(self, **overrides):
        options = dict(primary_reader=lambda _: copy.deepcopy(self.f.fixture.primary),
                       measurement_reader=lambda kind: copy.deepcopy(self.measurements[kind]),
                       raw_reader=lambda kind: copy.deepcopy(self.raw[kind]),
                       deployment_reader=lambda: copy.deepcopy(self.deployment),
                       decision_reader=lambda _: copy.deepcopy(self.review), authority=self.f.fixture.authority,
                       preflight=lambda: dict(ok=True, head=self.new, repository=str(self.candidate)),
                       **self.readers())
        options.update(overrides)
        return handoff.prepare(self.operating, self.candidate, self.plan, **options)

    def assert_unchanged(self):
        self.assertEqual(self.tree(self.operating), self.original)
        self.assertEqual(self.tree(self.candidate), self.candidate_original)

    def test_existing_valid_v2_baseline_uses_full_current_readers(self):
        value = handoff.baseline(self.operating, **self.readers())
        self.assertEqual(value['source_commit'], self.old)
        self.assertEqual(value['accepted_source_commit'], self.old)
        self.assertEqual(value['acceptance_schema'], ca.STABLE_SCHEMA)
        self.assertIn(('dependency', self.operating.resolve()), self.calls)
        self.assertIn(('worker', self.operating.resolve()), self.calls)
        self.assert_unchanged()

    def test_receipt_advanced_baseline_separates_anchor_and_runtime_head(self):
        self.sources[self.operating.resolve()] = self.f.append_receipt()
        self.original = self.tree(self.operating)
        value = handoff.baseline(self.operating, **self.readers())
        self.assertNotEqual(value['source_commit'], value['accepted_source_commit'])
        self.assertEqual(value['accepted_source_commit'], self.old)
        # Historical candidate audit uses the real accepted anchor; it does not
        # pretend the receipt HEAD is an accepted anchor or skip current readers.
        with self.assertRaisesRegex(ValueError, 'actual responding Worker'):
            self.prepare()
        self.assertIn(('worker', self.candidate.resolve()), self.calls)
        self.assert_unchanged()

    def test_private_probe_cannot_become_normal_v2_acceptance_even_dry_run(self):
        for dry in [True, False]:
            with self.subTest(dry=dry), patch.object(ca, 'issue', side_effect=AssertionError('MUST NOT ISSUE')):
                with self.assertRaisesRegex(ValueError, 'actual responding Worker'):
                    self.prepare(dry_run=dry)
        self.assert_unchanged()

    def test_missing_reader_refuses_before_candidate_or_operating_write(self):
        for field in ['dependency_reader', 'worker_reader']:
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'reader unavailable'):
                self.prepare(**{field: None})
        self.assert_unchanged()

    def test_reader_for_wrong_candidate_source_is_not_reused(self):
        def wrong(repo):
            value = self.dependency_reader(repo)
            value['source_commit'] = self.old
            return value
        with self.assertRaisesRegex(ValueError, 'dependency provenance'):
            self.prepare(dependency_reader=wrong)
        self.assert_unchanged()

    def test_runtime_binding_is_full_current_validation_after_receipt(self):
        self.sources[self.operating.resolve()] = self.f.append_receipt()
        self.original = self.tree(self.operating)
        proof = handoff.runtime_binding(self.operating, **self.readers())
        self.assertEqual(proof['schema'], 'NEW_A_VERIFIED_RUNTIME_PAIR_V2')
        self.assertEqual(proof['source_commit'], self.old)
        self.assertEqual(proof['runtime_source_commit'], self.sources[self.operating.resolve()])
        self.assertEqual(proof['acceptance_sha256'], self.anchor_record['sha256'])
        self.assert_unchanged()

    def test_runtime_new_worker_or_stale_metadata_refuses(self):
        for kind in ['new-worker', 'stale']:
            def changed(repo):
                value = self.worker_reader(repo)
                if kind == 'stale':
                    value['observed_at'] = '2026-11-16T11:54:00Z'
                else:
                    value['version_id'] = '00000000-0000-4000-8000-000000000099'
                    value['deployment_versions'] = [dict(version_id=value['version_id'], percentage=100)]
                return value
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                handoff.runtime_binding(self.operating, dependency_reader=self.dependency_reader, worker_reader=changed)
        self.assert_unchanged()

    def test_old_v1_owner_review_cannot_supply_v2_dry_run(self):
        self.review['decision'] = 'CONTINUING_DAILY_WITH_NONOWNER_UNMEASURED'
        with self.assertRaisesRegex(ValueError, 'intent or scope'):
            self.prepare()
        self.assert_unchanged()

    def test_missing_or_wrong_raw_http_refuses_without_writes(self):
        self.raw['owner']['api']['status'] = 403
        with self.assertRaisesRegex(ValueError, 'normal-response'):
            self.prepare()
        self.assert_unchanged()

    def test_source_change_during_current_validation_refuses(self):
        def changing(repo):
            value = self.dependency_reader(repo)
            if Path(repo).resolve() == self.operating.resolve():
                (self.operating / 'runtime.py').write_text('# concurrent dirty source\n')
            return value
        with self.assertRaisesRegex(ValueError, 'not clean'):
            handoff.baseline(self.operating, dependency_reader=changing, worker_reader=self.worker_reader)
        self.assertEqual(self.tree(self.candidate), self.candidate_original)
        self.assertEqual(self.f.fixture.activation.read_bytes(), (self.candidate / '.cache/weak_early_beta/new-a-private/activation.json').read_bytes())

    def test_already_deployed_python_api_forwards_v2_through_finite_apply_and_ready(self):
        # Separate API-wiring case, NOT a successful private-pretraffic release
        # or proof that global production traffic stayed on the old Worker.
        self.candidate_mode = 'NORMAL_PRODUCTION_URL_NO_OVERRIDE'
        self.deployment = dict(schema='NEW_A_HOST_VERIFIED_DEPLOYMENT_V1',
                               source_commit=self.new, target=self.f.fixture.target, version_id=self.version,
                               deployment_succeeded=True, deployed_at='2026-11-16T11:00:00Z',
                               observed_at='2026-11-16T11:30:00Z', raw_receipt_sha256=digest('synthetic deployed receipt'),
                               synthetic=False, platform_signature_claimed=False)
        receipt = self.prepare(dry_run=False)
        self.assertTrue(receipt['candidate_acceptance_written'])
        binding = handoff.handoff_binding(self.operating, self.candidate, receipt,
                                          deployment_reader=lambda: self.deployment, **self.readers())
        self.assertEqual(binding['schema'], 'NEW_A_RELEASE_CANDIDATE_BINDING_V2')
        self.assertEqual(binding['evidence_mode'], 'ALREADY_DEPLOYED_VERSION')
        self.assertEqual(binding['execution_identity_sha256'], digest(self.plan['execution_identity']))
        self.assertEqual(self.tree(self.operating), self.original)
        original = private_root(self.candidate) / 'continuing-acceptance/applications'
        self.assertGreater(len(list(original.glob('*/original.json'))), 1)
        with self.assertRaisesRegex(ValueError, 'reader unavailable'):
            handoff.verify_ready(self.operating, self.candidate, receipt,
                                  deployment_reader=lambda: self.deployment)
        changed = copy.deepcopy(self.deployment)
        changed['version_id'] = '00000000-0000-4000-8000-000000000099'
        with self.assertRaisesRegex(ValueError, 'deployed version changed'):
            handoff.verify_ready(self.operating, self.candidate, receipt,
                                  deployment_reader=lambda: changed, **self.readers())
        self.assertEqual(self.tree(self.operating), self.original)

    def test_current_python_runtime_proof_flows_to_js_without_starting(self):
        self.sources[self.operating.resolve()] = self.f.append_receipt()
        self.original = self.tree(self.operating)
        proof = handoff.runtime_binding(self.operating, **self.readers())
        pair = {k: v for k, v in proof.items() if k not in {'schema', 'runtime_source_commit'}}
        pair['schema'] = 'NEW_A_OPERATING_ACCEPTED_PAIR_V2'
        script = '''
import fs from 'node:fs';
import {execFileSync} from 'node:child_process';
import {acceptedLaunchPreflight} from './scripts/new-a-accepted-release.mjs';
const p=JSON.parse(fs.readFileSync(0,'utf8'));
const result=await acceptedLaunchPreflight({readPair:async()=>p.pair,
 verifyPair:async()=>p.proof,releaseInProgress:async()=>false,
 normalPreflight:async pair=>({ok:true,repository:pair.repository,
  head:execFileSync('git',['--no-optional-locks','rev-parse','HEAD'],{cwd:pair.repository,encoding:'utf8'}).trim()}),
 requireLatestHead:async()=>p.proof.runtime_source_commit});
console.log(JSON.stringify({head:result.head,starts:result.starts}));
'''
        result = subprocess.run([shutil.which('node'), '--input-type=module', '-e', script],
                                 input=json.dumps(dict(pair=pair, proof=proof)), text=True,
                                 capture_output=True, timeout=30, cwd=Path(__file__).resolve().parents[1])
        self.assertEqual(result.returncode, 0, result.stderr[-1000:])
        self.assertEqual(json.loads(result.stdout), dict(head=self.sources[self.operating.resolve()], starts=0))
        self.assert_unchanged()


if __name__ == '__main__':
    unittest.main()
