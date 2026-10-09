import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { probeFundamentalModel, run } from './weak-early-beta-daily-runner.mjs';
import { codexInvocation, loadFundamentalEnvironment, stampAnalysisStart, FUNDAMENTAL_MODEL, FUNDAMENTAL_REASONING_EFFORT } from './weak-early-beta-fundamental-runner.mjs';

test('Cloud child progress is readable before the process exits', async () => {
  const fixture = fs.mkdtempSync(path.join(os.tmpdir(), 'weak-early-beta-live-logs-'));
  try {
    const log = path.join(fixture, 'child');
    const script = path.join(fixture, 'child.mjs');
    fs.writeFileSync(script, `
console.log('phase started');
console.error('validation started');
await new Promise(resolve => setTimeout(resolve, 1200));
console.log('phase finished');
`);
    let finished = false;
    const pending = run(process.execPath, [script], {
      cwd: fixture, env: process.env, log, timeoutMs: 10000,
    }).finally(() => { finished = true; });
    for (let attempt = 0; attempt < 100; attempt++) {
      if (fs.readFileSync(`${log}.stderr`, 'utf8').includes('validation started')) break;
      await new Promise(resolve => setTimeout(resolve, 10));
    }
    assert.equal(finished, false);
    assert.equal(fs.readFileSync(`${log}.stdout`, 'utf8'), 'phase started\n');
    assert.equal(fs.readFileSync(`${log}.stderr`, 'utf8'), 'validation started\n');
    const result = await pending;
    assert.equal(result.code, 0);
    assert.equal(fs.readFileSync(`${log}.stdout`, 'utf8'), result.stdout);
    assert.equal(fs.readFileSync(`${log}.stderr`, 'utf8'), result.stderr);
  } finally {
    const resolved = path.resolve(fixture);
    if (!resolved.startsWith(`${path.resolve(os.tmpdir())}${path.sep}`) || !path.basename(resolved).startsWith('weak-early-beta-live-logs-')) {
      throw new Error('refusing to remove an unexpected fixture path');
    }
    fs.rmSync(resolved, { recursive: true, force: true });
  }
});

test('Cloud beta checks GPT-6.1 Sol xhigh with ChatGPT before detection', async () => {
  const parent = path.resolve(os.tmpdir());
  const fixture = fs.mkdtempSync(path.join(parent, 'weak-early-beta-model-preflight-'));
  try {
    const cliJs = path.join(fixture, 'fake-codex.mjs');
    fs.writeFileSync(cliJs, `
const args = process.argv.slice(2);
if (!args.includes('gpt-6.1-sol') || args.some(arg => /astra/i.test(arg)) ||
    !args.includes('model_reasoning_effort="xhigh"') ||
    !args.includes('forced_login_method="chatgpt"') ||
    process.env.OPENAI_API_KEY) process.exit(2);
if (process.env.FAIL_PROBE === '1') {
  console.log(JSON.stringify({ type: 'turn.failed' }));
  process.exit(1);
}
console.log(JSON.stringify({ type: 'turn.completed' }));
`);
    const fundamentalConfigPath = path.join(fixture, 'fundamental.json');
    fs.writeFileSync(fundamentalConfigPath, JSON.stringify({
      nodePath: process.execPath,
      cliJs,
      codexHome: fixture,
    }));
    const config = { fundamentalConfigPath };
    await probeFundamentalModel(config, path.join(fixture, 'success'), {
      ...process.env,
      OPENAI_API_KEY: 'must-not-reach-child',
      FAIL_PROBE: '0',
    });
    await assert.rejects(
      probeFundamentalModel(config, path.join(fixture, 'failure'), {
        ...process.env,
        OPENAI_API_KEY: 'must-not-reach-child',
        FAIL_PROBE: '1',
      }),
      /gpt-6\.1-sol xhigh model preflight failed/,
    );
  } finally {
    const resolved = path.resolve(fixture);
    if (!resolved.startsWith(`${parent}${path.sep}`) || !path.basename(resolved).startsWith('weak-early-beta-model-preflight-')) {
      throw new Error('refusing to remove an unexpected fixture path');
    }
    fs.rmSync(resolved, { recursive: true, force: true });
  }
});

test('configured native executable is used without the legacy JS CLI prefix', async () => {
  const legacy = codexInvocation({ nodePath: process.execPath, cliJs: 'legacy-cli.js' }, ['--search', '-m', FUNDAMENTAL_MODEL]);
  assert.deepEqual(legacy, { exe: process.execPath, args: ['legacy-cli.js', '--search', '-m', FUNDAMENTAL_MODEL] });
  const invocation = codexInvocation({ codexExecutable: process.execPath, nodePath: 'must-not-use', cliJs: 'must-not-prefix' },
    ['-e', 'process.stdout.write(JSON.stringify(process.argv.slice(1)))', '--', 'native-argv', FUNDAMENTAL_MODEL]);
  assert.equal(invocation.exe, path.resolve(process.execPath));
  assert.ok(!invocation.args.includes('must-not-prefix'));
  const fixture = fs.mkdtempSync(path.join(os.tmpdir(), 'weak-early-beta-native-invocation-'));
  try {
    const result = await run(invocation.exe, invocation.args, { cwd: fixture, env: process.env,
      log: path.join(fixture, 'native'), capture: true, timeoutMs: 10000 });
    assert.equal(result.code, 0);
    assert.deepEqual(JSON.parse(result.stdout), ['native-argv', FUNDAMENTAL_MODEL]);
    assert.throws(() => codexInvocation({ codexExecutable: path.join(fixture, 'missing.exe'), nodePath: process.execPath, cliJs: 'legacy' }, []), /do not substitute another runtime/);
    assert.throws(() => codexInvocation({ codexExecutable: '', nodePath: process.execPath, cliJs: 'legacy' }, []), /invalid configured native/);
  } finally {
    const resolved = path.resolve(fixture);
    if (!resolved.startsWith(`${path.resolve(os.tmpdir())}${path.sep}`) || !path.basename(resolved).startsWith('weak-early-beta-native-invocation-')) throw new Error('unexpected fixture path');
    fs.rmSync(resolved, { recursive: true, force: true });
  }
});

test('a newly started analysis updates retained claim model metadata; imports need no restamp', () => {
  const fixture = fs.mkdtempSync(path.join(os.tmpdir(), 'weak-early-beta-sol-model-stamp-'));
  try {
    const statePath = path.join(fixture, 'state.json');
    const alert = { alertId: 'weak-early-beta:2026-10-09:1234', signalType: 'WEAK_EARLY_BETA' };
    const claim = { claimId: 'owned', rules: { model: 'gpt-5.6-luna', reasoningEffort: 'xhigh', destination: 'html' }, alerts: [alert] };
    fs.writeFileSync(statePath, JSON.stringify({ claims: { [alert.alertId]: { claimId: 'owned' } } }));
    const stamped = stampAnalysisStart(statePath, claim, '2026-10-09T08:00:00.000Z');
    assert.equal(stamped.rules.model, FUNDAMENTAL_MODEL);
    assert.equal(stamped.rules.reasoningEffort, FUNDAMENTAL_REASONING_EFFORT);
    assert.equal(stamped.rules.destination, 'html');
    assert.equal(claim.rules.model, 'gpt-5.6-luna');
  } finally {
    const resolved = path.resolve(fixture);
    if (!resolved.startsWith(`${path.resolve(os.tmpdir())}${path.sep}`) || !path.basename(resolved).startsWith('weak-early-beta-sol-model-stamp-')) throw new Error('unexpected fixture path');
    fs.rmSync(resolved, { recursive: true, force: true });
  }
});

test('all dotenv layers are loaded before final API-key removal and every child receives the sanitized env', async () => {
  const fixture = fs.mkdtempSync(path.join(os.tmpdir(), 'weak-early-beta-sol-env-'));
  try {
    const repo = path.join(fixture, 'cloud');
    const premium = path.join(fixture, 'premium');
    fs.mkdirSync(repo, { recursive: true });
    fs.mkdirSync(path.join(premium, 'premium_worker'), { recursive: true });
    fs.writeFileSync(path.join(repo, '.env'), 'OPENAI_API_KEY=synthetic-root\nSOURCE_ROOT_MARKER=root\n');
    fs.writeFileSync(path.join(premium, '.env'), 'CODEX_API_KEY=synthetic-premium\nSOURCE_PREMIUM_MARKER=premium\n');
    fs.writeFileSync(path.join(premium, 'premium_worker', '.env'), 'openai_api_key=synthetic-worker\ncodex_api_key=synthetic-worker\nSOURCE_WORKER_MARKER=worker\n');
    const source = { PATH: process.env.PATH, OPENAI_API_KEY: 'synthetic-inherited' };
    const env = loadFundamentalEnvironment({ repoPath: repo, premiumWorkerRepoPath: premium,
      nodePath: process.execPath, codexHome: fixture }, source);
    assert.equal(source.OPENAI_API_KEY, 'synthetic-inherited');
    assert.equal(env.SOURCE_ROOT_MARKER, 'root');
    assert.equal(env.SOURCE_PREMIUM_MARKER, 'premium');
    assert.equal(env.SOURCE_WORKER_MARKER, 'worker');
    assert.equal(env.CODEX_HOME, fixture);
    assert.equal(Object.keys(env).some(key => /^(OPENAI_API_KEY|CODEX_API_KEY)$/i.test(key)), false);
    const result = await run(process.execPath, ['-e', `
if (Object.keys(process.env).some(key => /^(OPENAI_API_KEY|CODEX_API_KEY)$/i.test(key))) process.exit(7);
if (process.env.SOURCE_ROOT_MARKER !== 'root' || process.env.SOURCE_PREMIUM_MARKER !== 'premium' || process.env.SOURCE_WORKER_MARKER !== 'worker') process.exit(8);
console.log('SANITIZED_CHILD');
`], { cwd: fixture, env, log: path.join(fixture, 'sanitized-child'), capture: true, timeoutMs: 10000 });
    assert.equal(result.code, 0);
    assert.equal(result.stdout.trim(), 'SANITIZED_CHILD');
  } finally {
    const resolved = path.resolve(fixture);
    if (!resolved.startsWith(`${path.resolve(os.tmpdir())}${path.sep}`) || !path.basename(resolved).startsWith('weak-early-beta-sol-env-')) throw new Error('unexpected fixture path');
    fs.rmSync(resolved, { recursive: true, force: true });
  }
});
