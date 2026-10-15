import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import test from 'node:test';
import { JPX_SNAPSHOT, prepareJpxCheckout, checkpointJpxRefresh } from './weak-early-beta-jpx-checkout.mjs';

const branch = 'research/weak-early-beta';
const base = {
  version: 2, as_of: '2026-10-13', fetched_at: '2026-10-13T17:00:00+09:00',
  source_url: 'https://www.jpx.co.jp/listing/market-alerts/supervision/01.html', source_sha256: 'a'.repeat(64),
  rule: 'causal designation-date gate', symbols: [{ code: '1234', designation_date: '2026-10-01' }],
  delisted_symbols: [], delisting_history: [], relisted_symbols: [], delisting_sources: [],
  relisting_sources: [{ year: 2026, source_url: 'https://www.jpx.co.jp/listing/stocks/new/index.html', source_sha256: 'a'.repeat(64), listed_symbol_count: 41 }],
};
const refresh = (hour = 17) => ({ ...structuredClone(base), as_of: '2026-10-14', fetched_at: `2026-10-14T${hour}:00:00+09:00`, source_sha256: 'b'.repeat(64) });
const encode = value => JSON.stringify(value, null, 2) + '\n';

function fixture(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'cloud-jpx-test-'));
  t.after(() => {
    assert.ok(path.resolve(root).startsWith(path.resolve(os.tmpdir()) + path.sep));
    fs.rmSync(root, { recursive: true, force: true });
  });
  const repo = path.join(root, 'saved'), remote = path.join(root, 'origin.git');
  const rawGit = (cwd, args) => execFileSync('git', ['-c', 'core.autocrlf=false', ...args], { cwd, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] });
  fs.mkdirSync(repo);
  rawGit(root, ['init', '--bare', remote]);
  rawGit(repo, ['init', '-b', branch]);
  const configure = dir => {
    rawGit(dir, ['config', 'user.name', 'Cloud test']);
    rawGit(dir, ['config', 'user.email', 'cloud-test@example.invalid']);
    rawGit(dir, ['config', 'commit.gpgSign', 'false']);
    rawGit(dir, ['config', 'core.hooksPath', path.join(root, 'no-hooks')]);
  };
  configure(repo);
  fs.mkdirSync(path.dirname(path.join(repo, JPX_SNAPSHOT)), { recursive: true });
  fs.writeFileSync(path.join(repo, JPX_SNAPSHOT), encode(base));
  fs.writeFileSync(path.join(repo, '.gitignore'), '.cache/\n');
  rawGit(repo, ['add', '.']); rawGit(repo, ['commit', '-m', 'baseline']);
  rawGit(repo, ['remote', 'add', 'origin', remote]); rawGit(repo, ['push', '-u', 'origin', branch]);
  const calls = [];
  let safetyCalls = 0;
  const git = async args => {
    calls.push(args);
    const stdout = args[0] === 'remote' && args[1] === 'get-url' ? 'https://github.com/Ken5InvestmentLab/screening-bot.git\n' : rawGit(repo, args);
    return { stdout, code: 0, stderr: '' };
  };
  const write = value => fs.writeFileSync(path.join(repo, JPX_SNAPSHOT), encode(value));
  const head = () => rawGit(repo, ['rev-parse', 'HEAD']).trim();
  const remoteUpdate = value => {
    const other = path.join(root, 'other');
    rawGit(root, ['clone', '--branch', branch, remote, other]); configure(other);
    if (value) fs.writeFileSync(path.join(other, JPX_SNAPSHOT), encode(value));
    else fs.writeFileSync(path.join(other, 'completed-recovery.txt'), 'verified recovery\n');
    rawGit(other, ['add', '.']); rawGit(other, ['commit', '-m', 'remote recovery']);
    rawGit(other, ['push', 'origin', branch]);
    return rawGit(other, ['rev-parse', 'HEAD']).trim();
  };
  return {
    repo, calls, write, head, remoteUpdate, rawGit,
    options: { repo, git, checkSafety: () => { safetyCalls++; }, auditDir: path.join(repo, '.cache', 'jpx-audit') },
    safetyCalls: () => safetyCalls,
    clean: () => rawGit(repo, ['status', '--porcelain=v1']).trim() === '',
    pushed: () => rawGit(root, ['--git-dir', remote, 'rev-parse', `refs/heads/${branch}`]).trim(),
  };
}

test('superseded local metadata is audited and removed before fast-forwarding to the completed remote recovery', async t => {
  const f = fixture(t); f.write(refresh(17));
  const remote = f.remoteUpdate(refresh(18));
  const result = await prepareJpxCheckout(f.options);
  assert.equal(result.action, 'superseded'); assert.equal(result.committed, false);
  assert.equal(f.head(), remote); assert.ok(f.clean());
  assert.deepEqual(JSON.parse(fs.readFileSync(path.join(f.options.auditDir, 'jpx-before.json'))), refresh(17));
  assert.deepEqual(JSON.parse(fs.readFileSync(path.join(f.repo, JPX_SNAPSHOT))), refresh(18));
  assert.equal(f.calls.some(args => ['add', 'commit', 'push'].includes(args[0])), false);
});

test('a needed metadata refresh survives remote-only changes and is committed and pushed as one exact leaf', async t => {
  const f = fixture(t); f.write(refresh());
  const remote = f.remoteUpdate();
  const result = await prepareJpxCheckout(f.options);
  assert.equal(result.action, 'preserve'); assert.equal(result.committed, true);
  assert.equal(f.rawGit(f.repo, ['rev-parse', 'HEAD^']).trim(), remote);
  assert.deepEqual(f.rawGit(f.repo, ['diff-tree', '--no-commit-id', '--name-only', '-r', 'HEAD']).trim(), JPX_SNAPSHOT);
  assert.equal(f.head(), f.pushed()); assert.ok(f.clean());
  assert.equal(fs.readFileSync(path.join(f.repo, 'completed-recovery.txt'), 'utf8'), 'verified recovery\n');
});

test('a newer local refresh is preserved after a remote metadata refresh', async t => {
  const f = fixture(t); f.write(refresh(19)); f.remoteUpdate(refresh(18));
  const result = await prepareJpxCheckout(f.options);
  assert.equal(result.committed, true); assert.ok(f.clean());
  assert.equal(JSON.parse(fs.readFileSync(path.join(f.repo, JPX_SNAPSHOT))).fetched_at, refresh(19).fetched_at);
});

test('unknown edits, real symbol edits, malformed snapshots and staged files are preserved before any fetch', async t => {
  for (const kind of ['other', 'symbols', 'malformed', 'staged', 'older']) {
    const f = fixture(t); f.write(refresh());
    if (kind === 'other') fs.writeFileSync(path.join(f.repo, 'unrelated.txt'), 'user work');
    if (kind === 'symbols') { const value = refresh(); value.symbols = []; f.write(value); }
    if (kind === 'malformed') fs.writeFileSync(path.join(f.repo, JPX_SNAPSHOT), '{');
    if (kind === 'staged') f.rawGit(f.repo, ['add', JPX_SNAPSHOT]);
    if (kind === 'older') f.write({ ...refresh(), as_of: '2026-10-12' });
    const before = fs.readFileSync(path.join(f.repo, JPX_SNAPSHOT), 'utf8');
    await assert.rejects(prepareJpxCheckout(f.options));
    assert.equal(fs.readFileSync(path.join(f.repo, JPX_SNAPSHOT), 'utf8'), before);
    assert.equal(f.calls.some(args => ['fetch', 'restore', 'add', 'commit', 'push'].includes(args[0])), false);
  }
});

test('diverged branches preserve the local snapshot without restoring or committing it', async t => {
  const f = fixture(t); f.remoteUpdate();
  fs.writeFileSync(path.join(f.repo, 'local.txt'), 'local history');
  f.rawGit(f.repo, ['add', 'local.txt']); f.rawGit(f.repo, ['commit', '-m', 'local history']);
  f.write(refresh()); const before = f.head();
  await assert.rejects(prepareJpxCheckout(f.options));
  assert.equal(f.head(), before);
  assert.equal(f.calls.some(args => ['restore', 'add', 'commit', 'push'].includes(args[0])), false);
});

test('lock ownership loss blocks all repair mutations', async t => {
  const f = fixture(t); f.write(refresh());
  await assert.rejects(prepareJpxCheckout({ ...f.options, checkSafety: () => { throw Error('lock lost'); } }), /lock lost/);
  assert.equal(f.calls.length, 0);
});

test('a failed fast-forward restores a needed refresh instead of stranding it in ignored audit storage', async t => {
  const f = fixture(t); f.write(refresh()); f.remoteUpdate();
  await assert.rejects(prepareJpxCheckout({ ...f.options, git: async args => {
    if (args[0] === 'merge') throw new Error('simulated merge failure');
    return f.options.git(args);
  } }), /simulated merge failure/);
  assert.deepEqual(JSON.parse(fs.readFileSync(path.join(f.repo, JPX_SNAPSHOT))), refresh());
  assert.equal(f.calls.some(args => ['add', 'commit', 'push'].includes(args[0])), false);
});

test('remote and worktree races after inspection cannot push a JPX commit', async t => {
  for (const kind of ['remote', 'worktree']) {
    const f = fixture(t); f.write(refresh());
    let injected = false;
    await assert.rejects(prepareJpxCheckout({ ...f.options, git: async args => {
      if (!injected && args[0] === 'add') {
        injected = true;
        if (kind === 'remote') f.remoteUpdate();
        else fs.writeFileSync(path.join(f.repo, 'late-user-edit.txt'), 'concurrent work');
      }
      return f.options.git(args);
    } }));
    assert.equal(f.calls.some(args => ['commit', 'push'].includes(args[0])), false);
  }
});

test('a failed detector checkpoints only its own completed metadata refresh and leaves the checkout clean', async t => {
  const f = fixture(t), startedAt = new Date(Date.now() - 20_000).toISOString();
  const fetched = new Date(Date.now() - 5_000 + 9 * 3600_000).toISOString().replace('Z', '+09:00');
  const value = { ...refresh(), as_of: fetched.slice(0, 10), fetched_at: fetched };
  f.write(value);
  const result = await checkpointJpxRefresh({ ...f.options, startedAt, date: value.as_of, startCommit: f.head() });
  assert.equal(result.committed, true); assert.equal(f.head(), f.pushed()); assert.ok(f.clean());
});

test('failed detection cleanup rejects old timestamps, changed HEAD and mixed files without a commit', async t => {
  for (const kind of ['timestamp', 'head', 'mixed']) {
    const f = fixture(t); f.write(refresh());
    if (kind === 'mixed') fs.writeFileSync(path.join(f.repo, 'unrelated.txt'), 'user work');
    await assert.rejects(checkpointJpxRefresh({ ...f.options, startedAt: new Date().toISOString(), date: '2026-10-14', startCommit: kind === 'head' ? 'b'.repeat(40) : f.head() }));
    assert.equal(f.calls.some(args => ['restore', 'add', 'commit', 'push'].includes(args[0])), false);
  }
});
