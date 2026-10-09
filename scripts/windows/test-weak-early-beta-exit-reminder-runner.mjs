import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { loadReminderConfig, main } from './weak-early-beta-exit-reminder-runner.mjs';

const ledger = 'weak_early_beta/state/detections.csv';
const sha = 'a'.repeat(40);
const commitSha = 'c'.repeat(40);
const date = '2026-10-09';
const now = () => new Date('2026-10-08T22:30:00Z');

function fixture(t, settings = {}) {
  const repo = fs.mkdtempSync(path.join(os.tmpdir(), 'cloud-reminder-test-'));
  t.after(() => fs.rmSync(repo, { recursive: true, force: true }));
  const configPath = path.join(repo, 'config.json');
  fs.writeFileSync(configPath, JSON.stringify({ repoPath: repo, pythonPath: 'mock-python', ...settings.config }));
  const calls = [];
  const phases = [];
  let state = settings.initialStatus || '';
  let delivered = 0;
  let committed = false;
  const runImpl = async (exe, args) => {
    calls.push({ exe, args });
    let stdout = '';
    if (exe === 'mock-python') {
      assert.deepEqual(args, ['-B', '-m', 'weak_early_beta.cli', 'remind-exits', '--date', date]);
      delivered += 1;
      if (settings.childFailure) return { code: 1, stdout: '', stderr: 'delivery interrupted' };
      state = settings.deliveryStatus || (settings.reminders ? ` M ${ledger}\0` : '');
      stdout = JSON.stringify({ date, business_day: true, reminders: settings.reminders || 0, dry_run: false });
    } else if (exe === 'powershell.exe') {
      assert.ok(args.at(-1).includes('-ErrorAction Stop'));
      if (settings.processUnavailable) return { code: 1, stdout: '', stderr: 'Access denied' };
      stdout = settings.otherProcess || '';
    } else {
      assert.equal(exe, 'git');
      switch (args[0]) {
        case 'branch': stdout = (delivered && settings.deliveryBranch) || settings.branch || 'research/weak-early-beta'; break;
        case 'remote': stdout = settings.origin || 'https://github.com/Ken5InvestmentLab/screening-bot.git'; break;
        case 'rev-parse': stdout = args[1] === 'HEAD^' ? sha : committed ? commitSha : (delivered && settings.deliveryHead) || sha; break;
        case 'ls-remote': stdout = `${settings.remoteSha || sha}\trefs/heads/research/weak-early-beta\n`; break;
        case 'status': stdout = state; break;
        case 'add':
          assert.deepEqual(args, ['add', '--', ledger]);
          state = settings.normalizedNoop ? '' : `M  ${ledger}\0`;
          break;
        case 'diff': stdout = settings.normalizedNoop ? '' : `${ledger}\0`; break;
        case 'commit': state = ''; committed = true; break;
        case 'diff-tree': stdout = settings.commitLeaves || `${ledger}\0`; break;
        case 'push': assert.deepEqual(args, ['push', 'origin', `${commitSha}:refs/heads/research/weak-early-beta`]); break;
        default: throw new Error(`unexpected git operation ${args[0]}`);
      }
    }
    return { code: 0, stdout, stderr: '' };
  };
  return {
    repo, configPath, calls, phases, delivered: () => delivered,
    options: { runnerRepo: repo, runImpl, now, platform: settings.platform || 'linux', log: value => phases.push(value) },
    lock: path.join(repo, '.cache', 'weak_early_beta', 'exit-reminder-runner.lock'),
    resultPath: path.join(repo, '.cache', 'weak_early_beta', 'exit_reminder_runtime', 'exit-reminder-latest.json'),
  };
}

test('one reminder commits only the ledger and records every execution phase', async t => {
  const f = fixture(t, { reminders: 1 });
  const result = await main(f.configPath, f.options);
  assert.equal(result.ok, true);
  assert.equal(f.delivered(), 1);
  assert.equal(f.calls.filter(call => call.args[0] === 'commit').length, 1);
  assert.equal(f.calls.filter(call => call.args[0] === 'push').length, 1);
  assert.equal(f.calls.some(call => call.args.some(arg => arg.includes('reports/'))), false);
  assert.deepEqual(f.phases, ['preflight', 'delivery', 'receipt-sync', 'complete'].map(stage => `Cloud reminder stage: ${stage}`));
  assert.equal(fs.existsSync(f.lock), false);
  assert.equal(JSON.parse(fs.readFileSync(f.resultPath)).ok, true);
});

test('zero reminders stay silent without a commit or push', async t => {
  const f = fixture(t);
  const result = await main(f.configPath, f.options);
  assert.equal(result.reminders, 0);
  assert.equal(f.calls.some(call => ['add', 'commit', 'push'].includes(call.args[0])), false);
});

test('dirty, wrong branch, wrong origin and stale HEAD stop before any delivery', async t => {
  for (const settings of [
    { initialStatus: ' M reports/weak_early_beta_latest.html\0' },
    { branch: 'main' }, { origin: 'https://github.com/other/repo.git' }, { remoteSha: 'b'.repeat(40) },
  ]) {
    const f = fixture(t, settings);
    await assert.rejects(main(f.configPath, f.options));
    assert.equal(f.delivered(), 0);
    assert.equal(f.calls.some(call => ['add', 'commit', 'push'].includes(call.args[0])), false);
    assert.equal(fs.existsSync(f.lock), false);
    assert.equal(JSON.parse(fs.readFileSync(f.resultPath)).ok, false);
  }
});

test('cross-checkout config and replay dates cannot invoke any command', async t => {
  const f = fixture(t, { config: { date: '2026-10-08' } });
  await assert.rejects(main(f.configPath, f.options), /replay/);
  assert.equal(f.calls.length, 0);
  const other = fs.mkdtempSync(path.join(os.tmpdir(), 'cloud-reminder-other-'));
  t.after(() => fs.rmSync(other, { recursive: true, force: true }));
  assert.throws(() => loadReminderConfig(f.configPath, other), /mismatch/);
});

test('existing lock is preserved and another Windows reminder process blocks delivery', async t => {
  const f = fixture(t);
  fs.mkdirSync(path.dirname(f.lock), { recursive: true });
  fs.writeFileSync(f.lock, 'previous owner');
  await assert.rejects(main(f.configPath, f.options), /lock exists/);
  assert.equal(fs.readFileSync(f.lock, 'utf8'), 'previous owner');
  assert.equal(f.calls.length, 0);
  const other = fixture(t, { platform: 'win32', otherProcess: '1234' });
  await assert.rejects(main(other.configPath, other.options), /another/);
  assert.equal(other.delivered(), 0);
});

test('a child error is captured and never retried or followed by Git mutation', async t => {
  const f = fixture(t, { childFailure: true });
  await assert.rejects(main(f.configPath, f.options), /reconcile receipts/);
  assert.equal(f.delivered(), 1);
  assert.equal(f.calls.some(call => ['add', 'commit', 'push'].includes(call.args[0])), false);
  const saved = JSON.parse(fs.readFileSync(f.resultPath));
  assert.equal(saved.ok, false);
  assert.equal(saved.stage, 'delivery');
  assert.equal(fs.existsSync(f.lock), false);
});

test('unavailable Windows process inspection and an active daily lock stop before delivery', async t => {
  const unavailable = fixture(t, { platform: 'win32', processUnavailable: true });
  await assert.rejects(main(unavailable.configPath, unavailable.options), /process-preflight failed/);
  assert.equal(unavailable.delivered(), 0);
  const activeDaily = fixture(t);
  const dailyLock = path.join(activeDaily.repo, '.cache', 'weak_early_beta', 'daily_runtime', 'daily.lock');
  fs.mkdirSync(path.dirname(dailyLock), { recursive: true });
  fs.writeFileSync(dailyLock, 'daily owner');
  await assert.rejects(main(activeDaily.configPath, activeDaily.options), /another Cloud runner lock/);
  assert.equal(activeDaily.calls.length, 0);
  assert.equal(fs.readFileSync(dailyLock, 'utf8'), 'daily owner');
});

test('unrelated changes during delivery are preserved and block staging', async t => {
  const f = fixture(t, { reminders: 1, deliveryStatus: ` M ${ledger}\0 M reports/weak_early_beta_latest.html\0` });
  await assert.rejects(main(f.configPath, f.options), /unexpected change/);
  assert.equal(f.calls.some(call => ['add', 'commit', 'push'].includes(call.args[0])), false);
});

test('Windows normalized no-op receipt changes need no empty commit', async t => {
  const f = fixture(t, { reminders: 1, normalizedNoop: true });
  const result = await main(f.configPath, f.options);
  assert.equal(result.receiptCommit.committed, false);
  assert.equal(f.calls.some(call => ['commit', 'push'].includes(call.args[0])), false);
});

test('branch or HEAD changes during delivery block all staging and commits', async t => {
  for (const settings of [{ deliveryBranch: 'main' }, { deliveryHead: 'd'.repeat(40) }]) {
    const f = fixture(t, { reminders: 1, ...settings });
    await assert.rejects(main(f.configPath, f.options), /branch changed|HEAD|latest origin/);
    assert.equal(f.calls.some(call => ['add', 'commit', 'push'].includes(call.args[0])), false);
  }
});

test('a commit with an unexpected leaf cannot be pushed', async t => {
  const f = fixture(t, { reminders: 1, commitLeaves: `${ledger}\0.env\0` });
  await assert.rejects(main(f.configPath, f.options), /commit differs/);
  assert.equal(f.calls.some(call => call.args[0] === 'push'), false);
});
