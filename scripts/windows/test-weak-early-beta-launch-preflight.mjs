import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { launchPreflight } from './weak-early-beta-launch-preflight.mjs';

function fixture(t) {
  const repo = fs.mkdtempSync(path.join(os.tmpdir(), 'cloud-preflight-'));
  t.after(() => fs.rmSync(repo, { recursive: true, force: true }));
  const cache = path.join(repo, '.cache', 'weak_early_beta');
  fs.mkdirSync(cache, { recursive: true });
  fs.mkdirSync(path.join(repo, 'weak-early-beta-gate'));
  const write = (file, value) => fs.writeFileSync(file, JSON.stringify(value));
  const bin = path.join(repo, 'dummy-runtime');
  fs.writeFileSync(bin, 'fixture');
  fs.writeFileSync(path.join(repo, '.env'), 'DO_NOT_LOAD=private-marker');
  fs.writeFileSync(path.join(repo, 'weak-early-beta-gate', '.env'), 'DO_NOT_LOAD=private-marker');
  const workerFile = path.join(repo, 'weak-early-beta-gate', 'wrangler.jsonc');
  write(workerFile, { name: 'tentei-kyokuchi-cloud', vars: { DISCORD_API_BASE: 'https://discord.com/api/v10' } });
  const fundamental = path.join(cache, 'fundamental.json');
  write(fundamental, { repoPath: repo, runtimeDir: path.join(cache, 'fundamental_runtime'), codexExecutable: bin });
  const config = { repoPath: repo, runtimeDir: path.join(cache, 'daily_runtime'),
    fundamentalConfigPath: fundamental, pythonPath: bin, nodePath: bin, npmPath: bin, npmCliPath: bin };
  const file = path.join(cache, 'daily.json');
  write(file, config);
  const source = path.join(cache, 'tse_daily.csv');
  const quality = path.join(cache, 'tse_daily.source-quality.json');
  fs.writeFileSync(source, 'date,close\n2026-10-21,10\n');
  write(quality, { identity: 'CLOUD_SOURCE_QUALITY_V1', sourceRows: 1,
    daily_sha256: createHash('sha256').update(fs.readFileSync(source)).digest('hex') });
  const calls = [];
  const options = { repoRoot: repo, platform: 'win32', command(exe, args) {
    calls.push([exe, args]);
    if (exe === 'powershell.exe') return '';
    assert.equal(args[0], '--no-optional-locks');
    assert.ok(args.includes('core.fsmonitor=false'));
    if (args.includes('config')) return '';
    if (args.includes('branch')) return 'research/weak-early-beta';
    if (args.includes('remote')) return 'https://github.com/Ken5InvestmentLab/screening-bot.git';
    if (args.includes('status')) return '';
    if (args.includes('rev-parse')) return 'fixture-head';
    throw new Error('Unexpected external command');
  } };
  return { repo, cache, bin, file, config, fundamental, workerFile, source, quality, calls, options, write };
}

test('valid https origins survive preflight without loading secrets or creating a runtime', async t => {
  const f = fixture(t);
  const result = await launchPreflight(f.file, f.options);
  assert.equal(result.ok, true);
  assert.equal(result.sideEffects, false);
  assert.equal(result.npmExecutable, f.bin);
  assert.deepEqual(result.npmArgs, [f.bin, 'run', 'check']);
  assert.equal(fs.existsSync(f.config.runtimeDir), false);
  assert.equal(fs.existsSync(path.join(f.cache, 'fundamental_runtime')), false);
  assert.equal(JSON.stringify(result).includes('private-marker'), false);
  assert.equal(f.calls.every(([exe]) => ['git', 'powershell.exe'].includes(exe)), true);
});

test('another checkout config is rejected before external commands', async t => {
  const f = fixture(t);
  f.write(f.file, { ...f.config, repoPath: f.cache });
  await assert.rejects(launchPreflight(f.file, f.options), /repository mismatch/);
  assert.deepEqual(f.calls, []);
});

test('fundamental runtime cannot point outside its checkout', async t => {
  const f = fixture(t);
  f.write(f.fundamental, { repoPath: f.repo, runtimeDir: path.dirname(f.repo), codexExecutable: f.bin });
  await assert.rejects(launchPreflight(f.file, f.options), /another repository/);
  assert.deepEqual(f.calls, []);
});

test('wrong Worker and dirty checkout are hard stops', async t => {
  const f = fixture(t);
  f.write(f.workerFile, { name: 'scoring-bot-report' });
  await assert.rejects(launchPreflight(f.file, f.options), /Unexpected Cloud Worker/);
  f.write(f.workerFile, { name: 'tentei-kyokuchi-cloud' });
  const command = f.options.command;
  f.options.command = (exe, args) => args.includes('status') ? ' M unrelated.js' : command(exe, args);
  await assert.rejects(launchPreflight(f.file, f.options), /not clean/);
});

test('a reminder lock or an active runner prevents launch readiness', async t => {
  const f = fixture(t);
  const lock = path.join(f.cache, 'exit-reminder-runner.lock');
  fs.writeFileSync(lock, 'owned');
  await assert.rejects(launchPreflight(f.file, f.options), /lock exists/);
  fs.rmSync(lock);
  const command = f.options.command;
  f.options.command = (exe, args) => exe === 'powershell.exe' ? '1234' : command(exe, args);
  await assert.rejects(launchPreflight(f.file, f.options), /runner is already active/);
});

test('a changed cached byte fails against the original quality receipt', async t => {
  const f = fixture(t);
  fs.appendFileSync(f.source, '2026-10-22,20\n');
  await assert.rejects(launchPreflight(f.file, f.options), /source-quality receipt/);
});

test('a missing configured native CLI is never substituted', async t => {
  const f = fixture(t);
  f.write(f.fundamental, { repoPath: f.repo, runtimeDir: path.join(f.cache, 'fundamental_runtime'), codexExecutable: path.join(f.repo, 'missing') });
  await assert.rejects(launchPreflight(f.file, f.options), /ENOENT/);
  assert.deepEqual(f.calls, []);
});

test('real Git leaves the index unchanged when clean files have stale stat information', async t => {
  const f = fixture(t);
  const git = args => execFileSync('git', args, { cwd: f.repo, encoding: 'utf8', windowsHide: true }).trim();
  git(['init', '-b', 'research/weak-early-beta']);
  git(['remote', 'add', 'origin', 'https://github.com/Ken5InvestmentLab/screening-bot.git']);
  fs.writeFileSync(path.join(f.repo, '.gitignore'), '.cache/\n.env\nweak-early-beta-gate/.env\ndummy-runtime\n');
  git(['add', '.gitignore', 'weak-early-beta-gate/wrangler.jsonc']);
  git(['-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-m', 'fixture']);
  const sentinel = path.join(f.cache, 'external-helper-ran');
  const helper = path.join(f.cache, 'external-helper.cjs');
  fs.writeFileSync(helper, `require('node:fs').writeFileSync(${JSON.stringify(sentinel)}, 'ran');process.stdin.pipe(process.stdout);`);
  const helperCommand = `node "${helper.replaceAll('\\', '/')}"`;
  git(['config', 'core.fsmonitor', helperCommand]);
  git(['config', 'filter.probe.clean', helperCommand]);
  git(['config', 'filter.probe.process', helperCommand]);
  git(['config', 'filter.probe.required', 'true']);
  fs.writeFileSync(path.join(f.repo, '.git', 'info', 'attributes'), '*.jsonc filter=probe\n');
  const index = path.join(f.repo, '.git', 'index');
  const before = fs.readFileSync(index);
  fs.utimesSync(f.workerFile, new Date(), new Date(Date.now() + 10_000));
  f.options.command = (exe, args) => exe === 'powershell.exe' ? '' : git(args);
  assert.equal((await launchPreflight(f.file, f.options)).ok, true);
  assert.deepEqual(fs.readFileSync(index), before);
  assert.equal(fs.existsSync(sentinel), false);
});

test('PowerShell enumeration errors fail readiness instead of becoming an empty PID list', {
  skip: process.platform !== 'win32',
}, async t => {
  const f = fixture(t);
  const command = f.options.command;
  f.options.command = (exe, args) => {
    if (exe !== 'powershell.exe') return command(exe, args);
    assert.match(args.at(-1), /Get-CimInstance.*-ErrorAction Stop/);
    const failure = "function Get-CimInstance { [CmdletBinding()] param([string]$Filter) Write-Error 'fixture enumeration denied' }; ";
    return execFileSync(exe, [...args.slice(0, -1), failure + args.at(-1)], {
      encoding: 'utf8', windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'],
    }).trim();
  };
  await assert.rejects(launchPreflight(f.file, f.options), /Cloud runner process inspection failed/);
});
