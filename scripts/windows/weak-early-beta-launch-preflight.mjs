import fs from 'node:fs';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { loadDailyConfig, npmInvocation } from './weak-early-beta-daily-runner.mjs';

const runnerRepo = fileURLToPath(new URL('../../', import.meta.url));
const readJson = file => JSON.parse(fs.readFileSync(file, 'utf8').replace(/^\uFEFF/, ''));
const real = file => fs.realpathSync.native(file);

function inside(repo, file) {
  const relative = path.relative(repo, file);
  return relative !== '..' && !relative.startsWith(`..${path.sep}`) && !path.isAbsolute(relative);
}

async function sha256(file) {
  const hash = createHash('sha256');
  for await (const chunk of fs.createReadStream(file)) hash.update(chunk);
  return hash.digest('hex');
}

// Read-only: never create runtime directories, load credentials, probe a model,
// acquire prices, post Discord events, install dependencies or start a runner.
export async function launchPreflight(configFile, {
  repoRoot = runnerRepo,
  platform = process.platform,
  command = (exe, args, cwd) => execFileSync(exe, args, {
    cwd, encoding: 'utf8', windowsHide: true, timeout: 30_000,
  }).trim(),
} = {}) {
  const config = loadDailyConfig(configFile, repoRoot);
  const repo = real(config.repoPath);
  const configPath = real(path.resolve(configFile));
  if (!inside(repo, configPath)) throw new Error('Daily config is outside its repository');
  for (const key of ['runtimeDir', 'fundamentalConfigPath']) {
    if (!inside(repo, path.resolve(config[key]))) throw new Error(`${key} is outside the daily repository`);
  }
  // Existing directories can be junctions; reject realpath escapes as well.
  const runtimeParent = fs.existsSync(config.runtimeDir) ? config.runtimeDir : path.dirname(config.runtimeDir);
  if (!inside(repo, real(runtimeParent)) || !inside(repo, real(config.fundamentalConfigPath))) {
    throw new Error('Runtime or fundamental config realpath escapes the daily repository');
  }
  const fundamental = readJson(config.fundamentalConfigPath);
  if (real(fundamental.repoPath) !== repo || !inside(repo, path.resolve(fundamental.runtimeDir))) {
    throw new Error('Fundamental configuration targets another repository');
  }
  const fundamentalParent = fs.existsSync(fundamental.runtimeDir) ? fundamental.runtimeDir : path.dirname(fundamental.runtimeDir);
  if (!inside(repo, real(fundamentalParent))) throw new Error('Fundamental runtime realpath escapes the repository');
  for (const file of [config.pythonPath, config.nodePath, fundamental.codexExecutable,
    path.join(repo, '.env'), path.join(repo, 'weak-early-beta-gate', '.env')]) {
    if (typeof file !== 'string' || !fs.statSync(file).isFile()) throw new Error('Required Cloud runtime or environment file is missing');
  }
  // This tracked configuration is JSON. Do not strip // comments: that would
  // truncate https:// origins and turn valid configuration into invalid JSON.
  const worker = readJson(path.join(repo, 'weak-early-beta-gate', 'wrangler.jsonc'));
  if (worker.name !== 'tentei-kyokuchi-cloud') throw new Error('Unexpected Cloud Worker target');
  let gitOptions = ['--no-optional-locks', '-c', 'core.fsmonitor=false'];
  const git = (...args) => command('git', [...gitOptions, ...args], repo);
  // A readiness check must not invoke configured fsmonitor/clean-filter helpers.
  // Disable filter commands by argument, without changing any Git configuration.
  const drivers = new Set(git('config', '--null', '--name-only', '--list').split('\0')
    .map(key => key.match(/^filter\.(.+)\.(?:clean|process)$/i)?.[1]).filter(Boolean));
  for (const driver of drivers) gitOptions.push('-c', `filter.${driver}.clean=`,
    '-c', `filter.${driver}.process=`, '-c', `filter.${driver}.required=false`);
  if (git('branch', '--show-current') !== 'research/weak-early-beta') throw new Error('Unexpected Cloud branch');
  if (!/^(?:https:\/\/github\.com\/|git@github\.com:)Ken5InvestmentLab\/screening-bot(?:\.git)?$/i.test(git('remote', 'get-url', 'origin'))) {
    throw new Error('Unexpected Cloud origin');
  }
  if (git('status', '--porcelain=v1', '--untracked-files=all')) throw new Error('Daily checkout is not clean');
  const locks = [path.join(config.runtimeDir, 'daily.lock'),
    ...['.cache/weak_early_beta/exit-reminder-runner.lock', '.cache/weak_early_beta/exit-reminder.lock',
      'weak_early_beta/state/exit-reminder.lock', 'weak_early_beta/state/daily_runtime/daily.lock'].map(p => path.join(repo, p))];
  if (locks.some(file => fs.existsSync(file))) throw new Error('A Cloud daily or reminder lock exists');
  if (platform === 'win32') {
    const active = command('powershell.exe', ['-NoProfile', '-NonInteractive', '-Command',
      "try { $ErrorActionPreference = 'Stop'; @(Get-CimInstance Win32_Process -Filter \"Name = 'node.exe'\" -ErrorAction Stop | Where-Object { $_.CommandLine -match 'weak-early-beta-(?:daily|exit-reminder)-runner\\.mjs' } | Select-Object -ExpandProperty ProcessId) | ConvertTo-Json -Compress } catch { [Console]::Error.WriteLine('Cloud runner process inspection failed'); exit 1 }"], repo);
    if (active && !/^\[\s*\]$/.test(active)) throw new Error('A Cloud runner is already active');
  }
  const npm = npmInvocation(config, 'check', platform);
  const source = path.join(repo, '.cache', 'weak_early_beta', 'tse_daily.csv');
  const qualityFile = path.join(repo, '.cache', 'weak_early_beta', 'tse_daily.source-quality.json');
  const before = fs.statSync(source);
  const sourceSha256 = await sha256(source);
  const after = fs.statSync(source);
  const quality = readJson(qualityFile);
  if (quality.identity !== 'CLOUD_SOURCE_QUALITY_V1' || quality.daily_sha256 !== sourceSha256 ||
      before.size !== after.size || before.mtimeMs !== after.mtimeMs) {
    throw new Error('Cached source does not match its stable source-quality receipt');
  }
  return { ok: true, repository: repo, branch: 'research/weak-early-beta',
    head: git('rev-parse', 'HEAD'), worker: worker.name, sourceSha256,
    sourceRows: quality.sourceRows, npmExecutable: npm.exe, npmArgs: npm.args,
    modelAndNetworkPreflight: 'owned by the daily runner', sideEffects: false };
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  if (!process.argv[2]) throw new Error('usage: node weak-early-beta-launch-preflight.mjs <absolute-daily-config.json>');
  console.log(JSON.stringify(await launchPreflight(process.argv[2])));
}
