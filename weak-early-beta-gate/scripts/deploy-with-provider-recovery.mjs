import fs from 'node:fs';
import path from 'node:path';
import {spawn, execFileSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';

const MAX_WAIT_MS = 40 * 60_000;
const STATUS_ORIGIN = 'https://www.cloudflarestatus.com';
const READY = new Set(['monitoring', 'resolved']);

export function assetSessionFailure(output) {
  const text = String(output).replace(/\x1b\[[0-9;]*m/g, '');
  return /assets-upload-session\)[\s\S]{0,120}\bfailed\b/i.test(text) &&
    /(?:code:\s*10013\b|HTTP\s*50[0234]\b|Internal Server Error)/i.test(text) &&
    !/(?:unauthorized|forbidden|authentication|invalid API token|Current Version ID|Uploaded tentei-kyokuchi-cloud|Deployed tentei-kyokuchi-cloud)/i.test(text);
}

export function preparedBundleHash(gate) {
  const hash = createHash('sha256');
  const visit = (name) => {
    const file = path.join(gate, name), stat = fs.lstatSync(file);
    if (stat.isSymbolicLink()) throw Error('Unexpected symlink in prepared Cloud bundle');
    if (stat.isDirectory()) for (const entry of fs.readdirSync(file).sort()) visit(path.join(name, entry));
    else if (stat.isFile()) {hash.update(name.split(path.sep).join('/'));hash.update('\0');hash.update(fs.readFileSync(file));hash.update('\0');}
  };
  for (const name of ['src', 'public', 'wrangler.jsonc', 'package.json', 'package-lock.json']) visit(name);
  return hash.digest('hex');
}

export function assetIncidents(payload, now = Date.now()) {
  return (payload.incidents || []).filter(incident => {
    const created = Date.parse(incident.created_at);
    const text = [incident.name, ...(incident.incident_updates || []).map(update => update.body)].join('\n');
    return /^[a-z0-9]{5,32}$/.test(incident.id || '') && incident.status !== 'resolved' &&
      Number.isFinite(created) && created <= now && now - created <= 48 * 60 * 60_000 &&
      /workers(?: static)? assets?[^\n]{0,60}uploads?/i.test(text);
  });
}

// Only the unpublished asset-session boundary can be retried. Source data,
// script publication, Discord and the full daily runner never enter this loop.
export async function guardedDeploy({runDeploy, getStatus, getIncident, assertHead,
  wait = ms => new Promise(resolve => setTimeout(resolve, ms)), now = Date.now,
  maxWaitMs = MAX_WAIT_MS, pollMs = 60_000, onProgress = () => {}}) {
  if (!Number.isFinite(maxWaitMs) || maxWaitMs < 0 || maxWaitMs > MAX_WAIT_MS ||
      !Number.isFinite(pollMs) || pollMs <= 0 || pollMs > 60_000) throw Error('Invalid deployment recovery bounds');
  const deadline = now() + maxWaitMs;
  let attempts = 0;
  const progress = value => onProgress({...value, attempts, at: new Date(now()).toISOString()});
  const status = async () => {
    try { return assetIncidents(await getStatus(), now()); }
    catch { progress({phase: 'provider_status_unavailable'}); return null; }
  };
  const awaitRecovery = async incidents => {
    while (true) {
      const states = [];
      for (const expected of incidents) {
        const payload = await getIncident(expected.id);
        const incident = payload.incident || payload;
        if (incident.id !== expected.id || !incident.status) throw Error('Cloudflare incident identity unavailable');
        states.push({id: incident.id, status: incident.status, updatedAt: incident.updated_at});
      }
      if (states.every(incident => READY.has(incident.status))) {
        progress({phase: 'provider_recovered', incidents: states}); return;
      }
      progress({phase: 'waiting_external', incidents: states});
      if (now() >= deadline) throw Error('Cloudflare recovery wait exhausted; preserve this publication checkpoint');
      await wait(Math.min(pollMs, deadline - now()));
    }
  };
  await assertHead();
  const active = await status();
  if (active?.some(incident => !READY.has(incident.status))) await awaitRecovery(active);
  for (;;) {
    await assertHead();
    attempts++;
    progress({phase: 'deployment_start'});
    const result = await runDeploy();
    if (result.code === 0) { progress({phase: 'complete'}); return {ok: true, attempts}; }
    if (attempts >= 2 || !assetSessionFailure(result.output)) {
      progress({phase: 'failed', exitCode: result.code}); return {ok: false, attempts, code: result.code || 1};
    }
    const incidents = await status();
    if (!incidents?.length) {
      progress({phase: 'failed_no_confirmed_provider_incident', exitCode: result.code});
      return {ok: false, attempts, code: result.code || 1};
    }
    await awaitRecovery(incidents);
  }
}

async function main() {
  const gate = fileURLToPath(new URL('../', import.meta.url));
  const repo = path.dirname(gate.replace(/[\\/]$/, ''));
  const receiptPath = path.join(repo, '.cache/weak_early_beta/cloud-deploy-recovery.json');
  const receipt = {identity: 'CLOUD_DEPLOY_RECOVERY_V1', startedAt: new Date().toISOString(), ok: false, progress: []};
  const save = () => {
    fs.mkdirSync(path.dirname(receiptPath), {recursive: true});
    fs.writeFileSync(receiptPath + '.tmp', JSON.stringify(receipt, null, 2) + '\n');
    fs.renameSync(receiptPath + '.tmp', receiptPath);
  };
  try {
    const config = JSON.parse(fs.readFileSync(path.join(gate, 'wrangler.jsonc'), 'utf8'));
    if (config.name !== 'tentei-kyokuchi-cloud' || config.keep_vars !== true) throw Error('Unexpected Cloud Worker configuration');
    const git = args => execFileSync('git', args, {cwd: repo, encoding: 'utf8', windowsHide: true, timeout: 30_000}).trim();
    const expected = git(['rev-parse', 'HEAD']);
    if (process.env.GITHUB_ACTIONS === 'true') {
      if (process.env.GITHUB_REPOSITORY !== 'Ken5InvestmentLab/screening-bot' || process.env.GITHUB_SHA !== expected ||
          !String(process.env.GITHUB_REF || '').startsWith('refs/tags/cloud-deploy-')) throw Error('Unexpected deployment workflow ref');
    } else if (git(['branch', '--show-current']) !== 'research/weak-early-beta') throw Error('Unexpected deployment branch');
    receipt.headSha = expected;
    receipt.preparedBundleSha256 = preparedBundleHash(gate);
    const assertHead = () => {
      const remote = git(['ls-remote', 'origin', 'refs/heads/research/weak-early-beta']).split(/\s+/)[0];
      if (git(['rev-parse', 'HEAD']) !== expected || remote !== expected) throw Error('Research HEAD changed; refuse stale deployment');
      if (preparedBundleHash(gate) !== receipt.preparedBundleSha256) throw Error('Prepared Cloud bundle changed; refuse mixed publication');
    };
    const get = async url => {
      const response = await fetch(url, {signal: AbortSignal.timeout(30_000), headers: {'Cache-Control': 'no-cache'}});
      if (!response.ok) throw Error('Cloudflare status GET failed');
      return response.json();
    };
    const runDeploy = () => new Promise((resolve, reject) => {
      let output = '';
      const child = spawn(process.execPath, [path.join(gate, 'node_modules/wrangler/bin/wrangler.js'), 'deploy', '--env=', '--minify'],
        {cwd: gate, env: process.env, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe']});
      for (const [stream, destination] of [[child.stdout, process.stdout], [child.stderr, process.stderr]]) stream.on('data', chunk => {
        output = (output + chunk.toString()).slice(-2_000_000); destination.write(chunk);
      });
      child.once('error', reject);
      child.once('exit', code => resolve({code: code ?? 1, output}));
    });
    Object.assign(receipt, await guardedDeploy({runDeploy, assertHead,
      getStatus: () => get(STATUS_ORIGIN + '/api/v2/summary.json'),
      getIncident: id => get(STATUS_ORIGIN + '/api/v2/incidents/' + id + '.json'),
      onProgress: entry => {receipt.phase = entry.phase; receipt.progress.push(entry); save(); console.log(JSON.stringify({identity: 'CLOUD_DEPLOY_PHASE_V1', ...entry}));}}));
    if (!receipt.ok) process.exitCode = receipt.code || 1;
  } catch (error) { receipt.error = error.message; process.exitCode = 1; }
  finally { receipt.completedAt = new Date().toISOString(); save(); }
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) await main();
