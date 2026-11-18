import assert from 'node:assert/strict';
import test from 'node:test';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import {assetIncidents, assetSessionFailure, guardedDeploy, preparedBundleHash, standardDeploymentVersion} from '../weak-early-beta-gate/scripts/deploy-with-provider-recovery.mjs';
import {verifyOperationalLive} from '../weak-early-beta-gate/scripts/verify-operational-live.mjs';

const TIME = Date.parse('2026-10-29T11:00:00Z');
test('standard published version is exact, ANSI-safe and absent on missing or ambiguous output',()=>{const id='11111111-2222-3333-4444-555555555555';assert.equal(standardDeploymentVersion('Current Version ID: '+id),id);assert.equal(standardDeploymentVersion('\u001b[32mCurrent Version ID:\u001b[0m '+id),id);assert.equal(standardDeploymentVersion(''),null);assert.equal(standardDeploymentVersion('Current Version ID: bad'),null);assert.equal(standardDeploymentVersion('Current Version ID: '+id+'\nCurrent Version ID: '+id),null);});
const failure = {code: 1, output: 'A request to the Cloudflare API (/accounts/***/workers/scripts/tentei-kyokuchi-cloud/assets-upload-session) failed. [code: 10013]'};
const incident = status => ({id: 'abc12345', status, created_at: new Date(TIME - 1000).toISOString(),
  incident_updates: [{body: 'Elevated 500 errors affecting D1 and Workers Assets uploads.'}]});

function fixture(overrides = {}) {
  let time = TIME;
  const calls = {deploy: 0, waits: 0, heads: 0, progress: []};
  return {calls, options: {
    runDeploy: async () => {calls.deploy++; return {code: 0, output: ''};},
    getStatus: async () => ({incidents: []}),
    getIncident: async id => ({incident: {...incident('monitoring'), id}}),
    assertHead: async () => {calls.heads++;},
    now: () => time, wait: async ms => {calls.waits++; time += ms;},
    pollMs: 10, maxWaitMs: 20,
    onProgress: entry => calls.progress.push(entry), ...overrides,
  }};
}

test('healthy publication runs once and never polls for recovery', async () => {
  const f = fixture();
  assert.deepEqual(await guardedDeploy(f.options), {ok: true, attempts: 1});
  assert.equal(f.calls.deploy, 1); assert.equal(f.calls.waits, 0);
});

test('known outage is waited out BEFORE any asset session is created', async () => {
  let reads = 0;
  const f = fixture({getStatus: async () => ({incidents: [incident('identified')]}),
    getIncident: async () => ({incident: incident(reads++ ? 'monitoring' : 'identified')})});
  await guardedDeploy(f.options);
  assert.equal(f.calls.waits, 1); assert.equal(f.calls.deploy, 1);
  assert.equal(f.calls.progress[0].phase, 'waiting_external');
});

test('unpublished 10013 retries only after a confirmed provider recovery', async () => {
  let summaries = 0, reads = 0;
  const f = fixture({getStatus: async () => ({incidents: summaries++ ? [incident('identified')] : []}),
    getIncident: async () => incident(reads++ ? 'resolved' : 'identified')});
  f.options.runDeploy = async () => (++f.calls.deploy === 1 ? failure : {code: 0});
  assert.deepEqual(await guardedDeploy(f.options), {ok: true, attempts: 2});
  assert.equal(f.calls.waits, 1); assert.equal(f.calls.deploy, 2);
});

test('persistent 10013 cannot cause a third publication attempt', async () => {
  const f = fixture({getStatus: async () => ({incidents: [incident('monitoring')]})});
  f.options.runDeploy = async () => {f.calls.deploy++; return failure;};
  assert.deepEqual(await guardedDeploy(f.options), {ok: false, attempts: 2, code: 1});
  assert.equal(f.calls.deploy, 2);
});

test('10013 without an explicit current assets incident is not blindly retried', async () => {
  const f = fixture(); f.options.runDeploy = async () => {f.calls.deploy++; return failure;};
  assert.equal((await guardedDeploy(f.options)).ok, false);
  assert.equal(f.calls.deploy, 1); assert.equal(f.calls.waits, 0);
});

test('authentication, script-publication and ambiguous-success failures are not retryable', async () => {
  for (const output of ['Forbidden 403 ' + failure.output,
    'A request to the Cloudflare API (/workers/scripts/cloud/versions) failed. [code: 10013]',
    'Current Version ID: published\n' + failure.output]) {
    assert.equal(assetSessionFailure(output), false);
    const f = fixture({getStatus: async () => ({incidents: [incident('monitoring')]})});
    f.options.runDeploy = async () => {f.calls.deploy++; return {code: 1, output};};
    await guardedDeploy(f.options); assert.equal(f.calls.deploy, 1);
  }
});

test('unrelated or historical incidents cannot authorize another deployment', () => {
  assert.equal(assetIncidents({incidents: [{...incident('identified'), incident_updates: [{body: 'Images assets upload delays'}]}]}, TIME).length, 0);
  assert.equal(assetIncidents({incidents: [{...incident('identified'), incident_updates: [{body: 'Regional Durable Objects latency'}]}]}, TIME).length, 0);
  assert.equal(assetIncidents({incidents: [{...incident('identified'), created_at: new Date(TIME - 72 * 60 * 60_000).toISOString()}]}, TIME).length, 0);
  assert.equal(assetIncidents({incidents: [{...incident('identified'), id: '../other-host'}]}, TIME).length, 0);
});

test('unrecovered provider wait is bounded and starts no deployment', async () => {
  const f = fixture({getStatus: async () => ({incidents: [incident('identified')]}), getIncident: async () => incident('identified')});
  await assert.rejects(guardedDeploy(f.options), /wait exhausted/);
  assert.equal(f.calls.deploy, 0); assert.equal(f.calls.waits, 2);
});

test('a changed research ref after provider wait stops before publication', async () => {
  let heads = 0;
  const f = fixture({getStatus: async () => ({incidents: [incident('identified')]}),
    assertHead: async () => {if (++heads === 2) throw Error('Research HEAD changed');}});
  await assert.rejects(guardedDeploy(f.options), /HEAD changed/); assert.equal(f.calls.deploy, 0);
});

test('status outages preserve one normal attempt, but never grant a retry', async () => {
  const f = fixture({getStatus: async () => {throw Error('Status API unavailable');}});
  f.options.runDeploy = async () => {f.calls.deploy++; return failure;};
  assert.equal((await guardedDeploy(f.options)).ok, false); assert.equal(f.calls.deploy, 1);
});

test('invalid recovery bounds fail before any external work', async () => {
  for (const bounds of [{maxWaitMs: Infinity}, {maxWaitMs: 3_000_000}, {pollMs: 0}]) {
    const f = fixture(bounds); await assert.rejects(guardedDeploy(f.options), /bounds/); assert.equal(f.calls.deploy, 0);
  }
});

test('asset-session diagnostics allow line wrapping but not a later script failure', () => {
  assert.equal(assetSessionFailure(failure.output.replace(') failed', ')\nfailed')), true);
  assert.equal(assetSessionFailure('assets-upload-session) request succeeded\n' + 'x'.repeat(200) + 'failed [code: 10013]'), false);
});

test('prepared publication hash covers changes, additions and deletions', () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'cloud-publish-hash-'));
  try {
    for (const name of ['src', 'public']) fs.mkdirSync(path.join(directory, name));
    for (const name of ['wrangler.jsonc', 'package.json', 'package-lock.json']) fs.writeFileSync(path.join(directory, name), '{}');
    const before = preparedBundleHash(directory);
    fs.writeFileSync(path.join(directory, 'public', 'report.html'), 'one');
    const added = preparedBundleHash(directory);assert.notEqual(added, before);
    fs.writeFileSync(path.join(directory, 'public', 'report.html'), 'two');
    assert.notEqual(preparedBundleHash(directory), added);
    fs.unlinkSync(path.join(directory, 'public', 'report.html'));assert.equal(preparedBundleHash(directory), before);
  } finally {
    assert.ok(path.resolve(directory).startsWith(path.resolve(os.tmpdir()) + path.sep));
    assert.ok(path.basename(directory).startsWith('cloud-publish-hash-'));
    fs.rmSync(directory, {recursive: true, force: true});
  }
});

function liveReadbackFixture(select) {
  const head = 'a'.repeat(40);
  const version = '11111111-2222-3333-4444-555555555555';
  const build = 'b'.repeat(64);
  const receipt = {ok:true, headSha:head, versionId:version,
    operationalBuild:{source_commit:head, build_input_sha256:build}};
  const recording = {urls:[], waits:[]};
  const observe = () => verifyOperationalLive(receipt, head, {
    fetchImpl: async (url, options) => {
      recording.urls.push(url);
      const nonce = new URL(url).searchParams.get('new_a_probe');
      assert.equal(options.redirect,'error');
      assert.equal(options.headers['Cache-Control'],'no-cache');
      const expected = {schema:'NEW_A_OPERATIONAL_READBACK_V1', nonce, source_commit:head,
        version:{id:version,tag:head}, build_input_sha256:build, owner_http_observed:false,
        authentication_probe:false, d1_writes:0};
      return {url, status:200, headers:new Headers({'Cache-Control':'no-store'}),
        json:async()=>select(recording.urls.length,expected)};
    },
    wait: async ms => recording.waits.push(ms),
    nonce: () => String(recording.urls.length + 1).padStart(64,'0'),
  });
  return {recording, observe};
}

const priorReadback = expected => ({...expected, source_commit:'c'.repeat(40),
  version:{id:'99999999-7777-5555-3333-111111111111',tag:'c'.repeat(40)}, build_input_sha256:'d'.repeat(64)});

test('old edge version is observed again with a fresh nonce until exact new version appears', async () => {
  const {recording,observe}=liveReadbackFixture((attempt,expected)=>attempt<3?priorReadback(expected):expected);
  const result=await observe();
  assert.equal(result.source_commit,'a'.repeat(40));
  assert.deepEqual(recording.waits,[2000,4000]);
  assert.equal(new Set(recording.urls).size,3);
});

test('perpetually old version has a firm read-only verification limit', async () => {
  const {recording,observe}=liveReadbackFixture((_,expected)=>priorReadback(expected));
  await assert.rejects(observe(),/deployed Worker version in time/);
  assert.equal(recording.urls.length,5);
  assert.deepEqual(recording.waits,[2000,4000,8000,12000]);
});

test('integrity and same-version build mismatches are reported without retry', async () => {
  for (const [alter,error] of [
    [expected=>({...expected,nonce:'wrong'}),/integrity mismatch/],
    [expected=>({...expected,build_input_sha256:'e'.repeat(64)}),/different source or build/],
  ]) {
    const {recording,observe}=liveReadbackFixture((_,expected)=>alter(expected));
    await assert.rejects(observe(),error);
    assert.equal(recording.urls.length,1);
    assert.deepEqual(recording.waits,[]);
  }
});
