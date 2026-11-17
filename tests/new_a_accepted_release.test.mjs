// Entirely synthetic, private local files. No provider/owner browser/real Git.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {createHash, randomUUID} from 'node:crypto';
import {coordinateAcceptedRelease, acceptedLaunchPreflight, pairDigest} from '../scripts/new-a-accepted-release.mjs';
import {launchPreflight} from '../scripts/windows/weak-early-beta-launch-preflight.mjs';
import {requireRemoteHead} from '../scripts/windows/weak-early-beta-daily-runner.mjs';

const TIME = Date.parse('2026-11-18T00:00:00Z');
const OLD = 'c'.repeat(40), NEW = 'd'.repeat(40);
const target = {service:'tentei-kyokuchi-cloud',binding:'CLOUD_DB',database_name:'tentei-cloud-settings',database_id:'00000000-0000-4000-8000-000000000001'};
const clone = value => structuredClone(value);

function fixture(t) {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'new-a-handoff-synthetic-'));
  t.after(() => {
    const resolved = path.resolve(directory);
    assert.ok(resolved.startsWith(path.resolve(os.tmpdir()) + path.sep));
    assert.ok(path.basename(resolved).startsWith('new-a-handoff-synthetic-'));
    fs.rmSync(resolved,{recursive:true,force:true});
  });
  const file=path.join(directory,'selected-pair.json'),lock=path.join(directory,'release.lock'),operation=path.join(directory,'selection.json');
  const old={schema:'NEW_A_OPERATING_ACCEPTED_PAIR_V1',source_commit:OLD,
    worker_version_id:'00000000-0000-4000-8000-000000000001',target,
    acceptance_sha256:'b'.repeat(64),activation_sha256:'c'.repeat(64),repository:path.join(directory,'old')};
  const binding={schema:'NEW_A_RELEASE_CANDIDATE_BINDING_V1',source_commit:NEW,target,
    worker_version_id:'00000000-0000-4000-8000-000000000010',acceptance_sha256:'e'.repeat(64),
    activation_sha256:'f'.repeat(64),preparation_sha256:'a'.repeat(64),
    not_after:new Date(TIME+3600000).toISOString(),evidence_mode:'PRIVATE_PRETRAFFIC_PROBE',platform_signature_claimed:false};
  const write = value => {fs.writeFileSync(file+'.pending',JSON.stringify(value));fs.renameSync(file+'.pending',file);};
  write(old);fs.writeFileSync(path.join(directory,'old-pair-preserved.json'),JSON.stringify(old),{flag:'wx'});
  const calls={stage:0,select:0,head:0,proof:0};const trace=[];
  const f={directory,file,lock,old,binding,calls,trace,write,mode:'success',time:TIME,latest:NEW};
  const backend={capability:'PRIVATE_CANDIDATE_AND_ACCEPTED_PAIR_CAS_V1',
    acquire:async()=>{const lease=randomUUID();const fd=fs.openSync(lock,'wx');fs.writeFileSync(fd,lease);fs.closeSync(fd);return lease;},
    release:async lease=>{assert.equal(fs.readFileSync(lock,'utf8'),lease);fs.unlinkSync(lock);},
    readPair:async()=>JSON.parse(fs.readFileSync(file,'utf8')),
    readSelection:async()=>JSON.parse(fs.readFileSync(operation,'utf8')),
    selectPair:async({expectedDigest,proposed,lease})=>{
      calls.select++;assert.equal(fs.readFileSync(lock,'utf8'),lease);
      assert.equal(pairDigest(JSON.parse(fs.readFileSync(file,'utf8'))),expectedDigest);
      if(f.mode==='unknown'){fs.writeFileSync(operation,JSON.stringify({state:'UNKNOWN'}));throw Error('SYNTHETIC_TIMEOUT');}
      if(f.mode==='not-committed'){fs.writeFileSync(operation,JSON.stringify({state:'NOT_COMMITTED'}));throw Error('SYNTHETIC_REJECT');}
      write(proposed);
      fs.writeFileSync(operation,JSON.stringify({state:f.mode==='committed-unknown'?'UNKNOWN':'COMMITTED',pairDigest:pairDigest(proposed)}));
      if(f.mode==='lost-ack'||f.mode==='committed-unknown')throw Error('SYNTHETIC_LOST_ACK');
    }};
  f.backend=backend;
  f.options={expected:{source_commit:NEW,target},candidateRepository:path.join(directory,'new'),
    verifyCandidate:async()=>{calls.proof++;trace.push('proof');return clone(f.binding);},
    verifyPair:async pair=>pair?.schema==='NEW_A_OPERATING_ACCEPTED_PAIR_V1'&&sameTarget(pair.target)&&
      ((pair.source_commit===OLD&&pair.acceptance_sha256===old.acceptance_sha256&&pair.activation_sha256===old.activation_sha256)||
       (pair.source_commit===NEW&&pair.acceptance_sha256===binding.acceptance_sha256&&pair.activation_sha256===binding.activation_sha256)),
    backend,now:()=>f.time,audit:value=>trace.push(value.phase),
    ci:{stageOnly:true,assertHead:async()=>{calls.head++;assert.equal(f.latest,NEW);},
      runDeploy:async()=>{calls.stage++;trace.push('stage-only');return {code:0};},
      getStatus:async()=>({incidents:[]}),getIncident:async()=>{throw Error('UNEXPECTED_STATUS');},
      wait:async ms=>{f.time+=ms;},maxWaitMs:20,pollMs:10}};
  f.run=()=>coordinateAcceptedRelease(f.options);
  f.read=()=>JSON.parse(fs.readFileSync(file,'utf8'));
  f.assertOld=()=>{assert.deepEqual(f.read(),old);assert.deepEqual(JSON.parse(fs.readFileSync(path.join(directory,'old-pair-preserved.json'),'utf8')),old);};
  return f;
}
function sameTarget(value){return JSON.stringify(value)===JSON.stringify(target);}

test('proof precedes existing CI guardedDeploy and only a whole accepted pair is selected',async t=>{
  const f=fixture(t);const result=await f.run();
  assert.equal(result.status,'selected');assert.equal(result.selected.source_commit,NEW);
  assert.equal(result.selected.acceptance_sha256,f.binding.acceptance_sha256);
  assert.equal(f.calls.stage,1);assert.equal(f.calls.select,1);
  assert.ok(f.trace.indexOf('proof')<f.trace.indexOf('stage-only'));
  assert.equal(fs.existsSync(f.lock),false);assert.equal(result.starts,0);assert.equal(result.notifications,0);
});
test('missing formal adapter cannot fall back to ordinary traffic-changing Wrangler deploy',async t=>{
  const f=fixture(t);f.options.ci.stageOnly=false;
  await assert.rejects(f.run(),/ADAPTER_UNAVAILABLE/);assert.equal(f.calls.stage,0);f.assertOld();
});
test('old source and another target never enter CI publication',async t=>{
  for(const change of [{source_commit:OLD},{target:{...target,database_id:'OTHER'}}]){
    const f=fixture(t);Object.assign(f.binding,change);
    await assert.rejects(f.run(),/EXACT_PRIVATE/);assert.equal(f.calls.stage,0);f.assertOld();
  }
});
test('already deployed receipt is not relabelled as unpublished candidate proof',async t=>{
  const f=fixture(t);f.binding.evidence_mode='ALREADY_DEPLOYED_VERSION';
  await assert.rejects(f.run(),/EXACT_PRIVATE/);assert.equal(f.calls.stage,0);f.assertOld();
});
test('absent owner proof refuses all CI and selector work',async t=>{
  const f=fixture(t);f.options.verifyCandidate=async()=>{throw Error('NORMAL_RESPONSE_NOT_OBSERVED');};
  await assert.rejects(f.run(),/NOT_OBSERVED/);assert.equal(f.calls.stage,0);assert.equal(f.calls.select,0);f.assertOld();
});
test('changed acceptance and expiry are checked again after staging',async t=>{
  for(const mutate of [f=>{f.binding.acceptance_sha256='0'.repeat(64);},f=>{f.time+=3600001;}]){
    const f=fixture(t);f.options.ci.runDeploy=async()=>{f.calls.stage++;mutate(f);return {code:0};};
    await assert.rejects(f.run(),/CANDIDATE_ACCEPTANCE_CHANGED|EXACT_PRIVATE/);
    assert.equal(f.calls.select,0);f.assertOld();
  }
});
test('definitive stage failure preserves the known accepted pair',async t=>{
  const f=fixture(t);f.options.ci.runDeploy=async()=>{f.calls.stage++;return {code:1,output:'synthetic authentication failure'};};
  const result=await f.run();assert.equal(result.status,'old-retained');assert.equal(f.calls.stage,1);assert.equal(f.calls.select,0);f.assertOld();
});
test('existing unpublished-assets retry remains bounded and rechecks admission',async t=>{
  const f=fixture(t);const outage={id:'abc12345',status:'monitoring',created_at:new Date(TIME-1000).toISOString(),incident_updates:[{body:'Workers Assets uploads failure'}]};
  f.options.ci.getStatus=async()=>({incidents:[outage]});
  f.options.ci.getIncident=async()=>outage;
  f.options.ci.runDeploy=async()=>{f.calls.stage++;return f.calls.stage===1?{code:1,output:'assets-upload-session) failed [code: 10013]'}:{code:0};};
  const result=await f.run();assert.equal(result.status,'selected');assert.equal(f.calls.stage,2);assert.equal(f.calls.select,1);assert.ok(f.calls.proof>=4);
});
test('another deployment while waiting prevents any stage call',async t=>{
  const f=fixture(t);f.options.ci.getStatus=async()=>{f.write({...f.old,source_commit:'e'.repeat(40)});return {incidents:[]};};
  await assert.rejects(f.run(),/OPERATING_PAIR_CHANGED/);assert.equal(f.calls.stage,0);assert.equal(f.calls.select,0);
});
test('a stage adapter unexpectedly changing live state retains the lease, never rolls back',async t=>{
  const f=fixture(t);f.options.ci.runDeploy=async()=>{f.calls.stage++;f.write({...f.old,worker_version_id:f.binding.worker_version_id});return {code:0};};
  await assert.rejects(f.run(),/STAGE_CHANGED_LIVE_PAIR/);assert.equal(f.calls.select,0);assert.equal(fs.existsSync(f.lock),true);
});
test('unknown staging outcome preserves the lease and does not restage',async t=>{
  const f=fixture(t);f.options.ci.runDeploy=async()=>{f.calls.stage++;throw Error('SYNTHETIC_UNKNOWN_STAGE');};
  await assert.rejects(f.run(),/UNKNOWN_STAGE/);f.assertOld();assert.equal(fs.existsSync(f.lock),true);
  await assert.rejects(f.run(),/EEXIST/);assert.equal(f.calls.stage,1);assert.equal(f.calls.select,0);
});
test('CAS rejection with authoritative NOT_COMMITTED retains old pair',async t=>{
  const f=fixture(t);f.mode='not-committed';const result=await f.run();
  assert.equal(result.status,'old-retained');assert.equal(f.calls.select,1);assert.equal(fs.existsSync(f.lock),false);f.assertOld();
});
test('lost acknowledgement is resolved by readback without repeating the selection',async t=>{
  const f=fixture(t);f.mode='lost-ack';const result=await f.run();
  assert.equal(result.status,'selected');assert.equal(result.acknowledged,false);assert.equal(f.calls.stage,1);assert.equal(f.calls.select,1);
});
test('old or new pair alone cannot resolve an unknown selection',async t=>{
  for(const mode of ['unknown','committed-unknown']){
    const f=fixture(t);f.mode=mode;
    await assert.rejects(f.run(),/OUTCOME_UNKNOWN/);assert.equal(f.calls.select,1);assert.equal(fs.existsSync(f.lock),true);
    await assert.rejects(f.run(),/EEXIST/);assert.equal(f.calls.stage,1);assert.equal(f.calls.select,1);
  }
});
test('concurrent deployment is excluded by an observed in-flight stage barrier',async t=>{
  const f=fixture(t);let enter,release;const entered=new Promise(resolve=>enter=resolve),wait=new Promise(resolve=>release=resolve);
  f.options.ci.runDeploy=async()=>{f.calls.stage++;enter();await wait;return {code:0};};
  const first=f.run();await entered;
  await assert.rejects(f.run(),/EEXIST/);f.assertOld();assert.equal(f.calls.stage,1);
  release();assert.equal((await first).status,'selected');
});

function launchFixture(f, pair){
  const repo=pair.repository,cache=path.join(repo,'.cache','weak_early_beta');fs.mkdirSync(cache,{recursive:true});
  fs.mkdirSync(path.join(repo,'weak-early-beta-gate'));
  const write=(name,value)=>fs.writeFileSync(name,JSON.stringify(value));
  const bin=path.join(repo,'synthetic-runtime.bin');fs.writeFileSync(bin,'SYNTHETIC');
  fs.writeFileSync(path.join(repo,'.env'),'');fs.writeFileSync(path.join(repo,'weak-early-beta-gate','.env'),'');
  write(path.join(repo,'weak-early-beta-gate','wrangler.jsonc'),{name:'tentei-kyokuchi-cloud'});
  const config=path.join(cache,'daily.json');write(config,{repoPath:repo,runtimeDir:path.join(cache,'daily_runtime'),pythonPath:bin,nodePath:bin,npmPath:bin,npmCliPath:bin,fundamentalConfigPath:path.join(cache,'unused.json')});
  const csv=path.join(cache,'tse_daily.csv');fs.writeFileSync(csv,'date,close\n2026-11-17,10\n');
  write(path.join(cache,'tse_daily.source-quality.json'),{identity:'CLOUD_SOURCE_QUALITY_V1',sourceRows:1,daily_sha256:createHash('sha256').update(fs.readFileSync(csv)).digest('hex')});
  f.dirty=false;
  const command=(_exe,args)=>args.includes('config')?'':args.includes('branch')?'research/weak-early-beta':args.includes('remote')?'https://github.com/Ken5InvestmentLab/screening-bot.git':args.includes('status')?(f.dirty?' M other.py':''):args.includes('rev-parse')?pair.source_commit:(()=>{throw Error('UNEXPECTED_COMMAND');})();
  return {readPair:f.backend.readPair,verifyPair:f.options.verifyPair,releaseInProgress:async()=>fs.existsSync(f.lock),
    normalPreflight:async()=>{const ready=await launchPreflight(config,{repoRoot:repo,strategy:'A_BASE',platform:'linux',command});assert.equal(ready.head,pair.source_commit);assert.equal(ready.repository,fs.realpathSync.native(repo));return ready;},
    requireLatestHead:()=>requireRemoteHead(async args=>({stdout:args[0]==='rev-parse'?pair.source_commit:`${f.latest}\trefs/heads/research/weak-early-beta`}))};
}
test('selected new pair passes the actual read-only launchPreflight and requireRemoteHead',async t=>{
  const f=fixture(t);await f.run();const options=launchFixture(f,f.read());
  const result=await acceptedLaunchPreflight(options);assert.equal(result.head,NEW);assert.equal(result.starts,0);
});
test('retained old pair is not permission to skip the latest-remote-HEAD check',async t=>{
  const f=fixture(t);const options=launchFixture(f,f.old);
  await assert.rejects(acceptedLaunchPreflight(options),/latest origin/);f.assertOld();
  f.latest=OLD;assert.equal((await acceptedLaunchPreflight(options)).head,OLD);
});
test('dirty checkout is still rejected by the existing ordinary preflight',async t=>{
  const f=fixture(t);await f.run();const options=launchFixture(f,f.read());f.dirty=true;
  await assert.rejects(acceptedLaunchPreflight(options),/not clean/);
});
test('realpath normalization never accepts another physical repository',async t=>{
  const f=fixture(t);await f.run();const options=launchFixture(f,f.read());
  const normal=options.normalPreflight;options.normalPreflight=async()=>({...await normal(),repository:f.directory});
  await assert.rejects(acceptedLaunchPreflight(options),/REPOSITORY_MISMATCH/);
});
test('handoff lock blocks launch before any normal preflight work',async t=>{
  const f=fixture(t);const options=launchFixture(f,f.old);const lease=await f.backend.acquire();
  options.normalPreflight=()=>assert.fail('MUST NOT REACH PREFLIGHT');
  await assert.rejects(acceptedLaunchPreflight(options),/IN_PROGRESS/);await f.backend.release(lease);
});
test('runtime-only or acceptance-only partial change is never accepted for launch',async t=>{
  for(const mutate of [p=>({...p,source_commit:NEW}),p=>({...p,acceptance_sha256:'e'.repeat(64)})]){
    const f=fixture(t);const options=launchFixture(f,f.old);f.write(mutate(f.old));
    await assert.rejects(acceptedLaunchPreflight(options),/ACCEPTANCE_INVALID/);
  }
});
test('pair change during normal preflight refuses readiness without any start',async t=>{
  const f=fixture(t);const options=launchFixture(f,f.old);f.latest=OLD;
  const normal=options.normalPreflight;options.normalPreflight=async()=>{const result=await normal();f.write({...f.old,worker_version_id:f.binding.worker_version_id});return result;};
  await assert.rejects(acceptedLaunchPreflight(options),/CHANGED_BEFORE_LAUNCH/);
});
