"""Synthetic host probe -> real formal Python acceptance -> real CI JS guard.

No real provider adapter is installed. All authority/network evidence is mocked;
temporary accepted candidates and an in-memory transactional backend are used.
"""
import copy
import json
import shutil
import subprocess
import unittest
from pathlib import Path

from tests import test_new_a_release_acceptance as fixtures
from weak_early_beta.new_a import release_acceptance as handoff
from weak_early_beta.new_a.files import private_root, read


class ReleaseIntegration(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.ReleaseAcceptance()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        value = self.f.deployment
        value.update(schema='NEW_A_HOST_VERIFIED_PRIVATE_CANDIDATE_PROBE_V1',
                     deployment_succeeded=False, uploaded_only=True,
                     live_traffic_percent=0, normal_protected_probe=True,
                     existing_owner_authorization=True, access_policy_unchanged=True,
                     public_preview=False, version_available_at=value.pop('deployed_at'))

    def test_pretraffic_probe_is_explicitly_not_a_successful_deployment(self):
        value = self.f.prepare(dry_run=False)
        self.assertFalse(value['deployment']['deployment_succeeded'])
        binding = handoff.handoff_binding(self.f.operating, self.f.candidate, value,
                                          deployment_reader=lambda: self.f.deployment)
        self.assertEqual(binding['evidence_mode'], 'PRIVATE_PRETRAFFIC_PROBE')
        self.f.assert_old_operates()

    def test_claimed_deployed_or_public_preview_is_not_the_missing_probe(self):
        for key, value in [('deployment_succeeded', True), ('uploaded_only', False),
                           ('live_traffic_percent', 1), ('normal_protected_probe', False),
                           ('existing_owner_authorization', False),
                           ('access_policy_unchanged', False), ('public_preview', True)]:
            with self.subTest(key=key):
                before = copy.deepcopy(self.f.deployment)
                self.f.deployment[key] = value
                self.f.reject('private pretraffic probe')
                self.f.deployment = before

    def test_no_probe_reader_means_no_candidate_or_operating_update(self):
        self.f.reject('independent deployment reader', deployment_reader=None)

    def test_formal_accepted_candidate_binding_flows_through_existing_ci_guard(self):
        value = self.f.prepare(dry_run=False)
        binding = handoff.handoff_binding(self.f.operating, self.f.candidate, value,
                                          deployment_reader=lambda: self.f.deployment)
        old = read(private_root(self.f.operating) / 'activation.json')
        payload = dict(binding=binding, old=dict(schema='NEW_A_OPERATING_ACCEPTED_PAIR_V1',
                       source_commit=self.f.old, worker_version_id='00000000-0000-4000-8000-000000000001',
                       target=self.f.f.target, acceptance_sha256=old['owner_acceptance']['continuing_acceptance']['sha256'],
                       activation_sha256=value['operating_baseline']['activation_sha256'],
                       repository=str(self.f.operating)), candidate=str(self.f.candidate))
        script = r'''
import fs from 'node:fs';
import {coordinateAcceptedRelease,pairDigest} from './scripts/new-a-accepted-release.mjs';
const p=JSON.parse(fs.readFileSync(0,'utf8'));let selected=structuredClone(p.old),operation,stages=0,selections=0,held=false;
const backend={capability:'PRIVATE_CANDIDATE_AND_ACCEPTED_PAIR_CAS_V1',
 acquire:async()=>{if(held)throw Error('BUSY');held=true;return 'SYNTHETIC_LEASE';},
 release:async()=>{held=false;},readPair:async()=>structuredClone(selected),readSelection:async()=>operation,
 selectPair:async({expectedDigest,proposed})=>{if(pairDigest(selected)!==expectedDigest)throw Error('CAS');selected=structuredClone(proposed);operation={state:'COMMITTED',pairDigest:pairDigest(selected)};selections++;}};
const result=await coordinateAcceptedRelease({expected:{source_commit:p.binding.source_commit,target:p.binding.target},candidateRepository:p.candidate,
 verifyCandidate:async()=>p.binding,verifyPair:async pair=>pair.source_commit===p.old.source_commit?pair.acceptance_sha256===p.old.acceptance_sha256:pair.source_commit===p.binding.source_commit&&pair.acceptance_sha256===p.binding.acceptance_sha256,
 backend,now:()=>Date.parse(p.binding.not_after)-60000,
 ci:{stageOnly:true,assertHead:async()=>{},runDeploy:async()=>{stages++;if(selected.source_commit!==p.old.source_commit)throw Error('EARLY_SWITCH');return {code:0};},
 getStatus:async()=>({incidents:[]}),getIncident:async()=>{throw Error('NO_NETWORK');},maxWaitMs:0,pollMs:1}});
console.log(JSON.stringify({status:result.status,source:selected.source_commit,acceptance:selected.acceptance_sha256,stages,selections,starts:result.starts,notifications:result.notifications,held}));
'''
        completed = subprocess.run([shutil.which('node'), '--input-type=module', '-e', script],
                                   input=json.dumps(payload), text=True, capture_output=True,
                                   cwd=Path(__file__).resolve().parents[1], timeout=30)
        self.assertEqual(completed.returncode, 0, completed.stderr[-1500:])
        result = json.loads(completed.stdout)
        self.assertEqual(result, dict(status='selected', source=self.f.new,
                         acceptance=binding['acceptance_sha256'], stages=1, selections=1,
                         starts=0, notifications=0, held=False))
        self.f.assert_old_operates()


if __name__ == '__main__':
    unittest.main()
