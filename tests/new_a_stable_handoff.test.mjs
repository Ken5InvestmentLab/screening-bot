// Synthetic in-memory handoff and temporary directories; no real adapters.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {coordinateAcceptedRelease, acceptedLaunchPreflight} from '../scripts/new-a-accepted-release.mjs';

const clone=value=>structuredClone(value),OLD='c'.repeat(40),CURRENT='d'.repeat(40),NEXT='e'.repeat(40);
const target={service:'tentei-kyokuchi-cloud',binding:'CLOUD_DB',database_name:'tentei-cloud-settings',database_id:'00000000-0000-4000-8000-000000000001'};
function fixture(t){
 const root=fs.mkdtempSync(path.join(os.tmpdir(),'stable-handoff-mock-'));
 t.after(()=>{assert(path.resolve(root).startsWith(path.resolve(os.tmpdir())+path.sep));fs.rmSync(root,{recursive:true,force:true});});
 const pair={schema:'NEW_A_OPERATING_ACCEPTED_PAIR_V2',source_commit:OLD,target,repository:root,
  worker_version_id:'00000000-0000-4000-8000-000000000002',worker_artifact_sha256:'a'.repeat(64),
  execution_identity_sha256:'b'.repeat(64),acceptance_sha256:'f'.repeat(64),activation_sha256:'0'.repeat(64)};
 const proof={...clone(pair),schema:'NEW_A_VERIFIED_RUNTIME_PAIR_V2',runtime_source_commit:CURRENT};
 const calls={normal:0,latest:0,stages:0,selections:0,proof:0};
 const options={readPair:async()=>clone(pair),verifyPair:async()=>{calls.proof++;return clone(proof);},
  releaseInProgress:async()=>false,
  normalPreflight:async runtime=>{calls.normal++;assert.equal(runtime.source_commit,CURRENT);assert.equal(runtime.accepted_source_commit,OLD);return{ok:true,head:CURRENT,repository:root};},
  requireLatestHead:async runtime=>{calls.latest++;assert.equal(runtime.source_commit,CURRENT);return CURRENT;}};
 return{pair,proof,calls,options};
}

test('existing V2 current lineage proof reaches normal preflight/current remote HEAD without launch',async t=>{
 const f=fixture(t),result=await acceptedLaunchPreflight(f.options);
 assert.equal(result.head,CURRENT);assert.equal(result.starts,0);assert.equal(f.calls.normal,1);assert.equal(f.calls.proof,2);
});

test('a V2 pair cannot use a V1 boolean or partial identity as current proof',async t=>{
 for(const proof of[true,{schema:'NEW_A_VERIFIED_RUNTIME_PAIR_V2',runtime_source_commit:CURRENT}]){
  const f=fixture(t);f.options.verifyPair=async()=>proof;
  await assert.rejects(acceptedLaunchPreflight(f.options),/SELECTED_V2_RUNTIME_PROOF_INVALID/);assert.equal(f.calls.normal,0);
 }
});

test('wrong anchor/Worker/artifact/target/repository is rejected before ordinary preflight',async t=>{
 for(const[key,value]of Object.entries({source_commit:NEXT,worker_version_id:'00000000-0000-4000-8000-000000000099',
  worker_artifact_sha256:'9'.repeat(64),execution_identity_sha256:'9'.repeat(64),target:{...target,database_id:'OTHER'},repository:os.tmpdir()})){
  const f=fixture(t);f.proof[key]=value;
  await assert.rejects(acceptedLaunchPreflight(f.options),/SELECTED_V2_RUNTIME_PROOF_INVALID/);assert.equal(f.calls.normal,0);
 }
});

test('Worker change during preflight refuses readiness without starting',async t=>{
 const f=fixture(t),normal=f.options.normalPreflight;
 f.options.normalPreflight=async pair=>{const ready=await normal(pair);f.proof.worker_artifact_sha256='9'.repeat(64);return ready;};
 await assert.rejects(acceptedLaunchPreflight(f.options),/V2_RUNTIME_PROOF_INVALID/);
});

test('release lock and latest remote checks still block V2 runtime readiness',async t=>{
 const f=fixture(t);f.options.releaseInProgress=async()=>true;
 await assert.rejects(acceptedLaunchPreflight(f.options),/IN_PROGRESS/);assert.equal(f.calls.normal,0);
 f.options.releaseInProgress=async()=>false;f.options.requireLatestHead=async()=>NEXT;
 await assert.rejects(acceptedLaunchPreflight(f.options),/LATEST_RESEARCH_HEAD_REQUIRED/);
});

test('V2 normal proof is not relabelled as a private pretraffic transaction',async t=>{
 for(const evidence_mode of['ALREADY_DEPLOYED_VERSION','PRIVATE_PRETRAFFIC_PROBE']){
  const f=fixture(t),old=clone(f.pair);let selected=clone(old),held=false;
  const binding={schema:'NEW_A_RELEASE_CANDIDATE_BINDING_V2',source_commit:NEXT,target,evidence_mode};
  await assert.rejects(coordinateAcceptedRelease({expected:{source_commit:NEXT,target},candidateRepository:f.pair.repository,
   verifyCandidate:async()=>binding,verifyPair:async()=>true,
   backend:{capability:'PRIVATE_CANDIDATE_AND_ACCEPTED_PAIR_CAS_V1',acquire:async()=>{held=true;return'lease';},
    release:async()=>{held=false;},readPair:async()=>clone(selected),readSelection:async()=>({state:'NOT_COMMITTED'}),
    selectPair:async()=>{f.calls.selections++;}},
   ci:{stageOnly:true,assertHead:async()=>{},runDeploy:async()=>{f.calls.stages++;return{code:0};}}}),
   /V2_NORMAL_PROOF_PRETRAFFIC_CONTRACT_UNAVAILABLE/);
  assert.deepEqual(selected,old);assert.equal(held,false);assert.equal(f.calls.stages,0);assert.equal(f.calls.selections,0);
 }
});
