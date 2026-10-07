import { spawnSync } from 'node:child_process';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import {
  assertGeneratedChanges,
  assertHtmlImports,
  assertValidatedFundamentalOutput,
  commitGeneratedChanges,
  drainFundamentalQueue,
  npmInvocation,
  parseGitStatus,
  queueIdentities,
  reconcileNotifications,
  requireRemoteHead,
  selectWorkflowRun,
  verifyLiveWorker,
  waitForTagWorkflow,
} from './weak-early-beta-daily-runner.mjs';

const generatedReport = 'reports/weak_early_beta_latest.html';
const signalDate = '2026-10-06';
const tag = 'cloud-deploy-test-20261006';
const headSha = 'a'.repeat(40);
const origin = 'https://tentei-kyokuchi-cloud.ipo-ken5-5489.workers.dev';

test('the generated commit used for tag deployment contains no workflow skip instruction', () => {
  const source = fs.readFileSync(new URL('./weak-early-beta-daily-runner.mjs', import.meta.url), 'utf8');
  const generatedMessage = source.match(/result\.generatedCommit = await commitGeneratedChanges\(\{ git, message: `([^`]+)`/);
  assert.ok(generatedMessage, 'the live generated-commit message must be checked');
  assert.doesNotMatch(generatedMessage[1], /\[(?:skip ci|ci skip|no ci|skip actions|actions skip)\]|skip-checks\s*:/i);
});

function queueItem(symbol) {
  return { signal_date: signalDate, symbol, claim_id: `${signalDate}|${symbol}` };
}

function childReceipt({ ok = true, claimed = 1, imported = claimed, code = 0 } = {}) {
  return {
    code,
    stdout: `child progress\n${JSON.stringify({
      identity: 'WEAK_EARLY_FUNDAMENTAL_LUNA_XHIGH_V1', ok, claimed, imported, posted: 0,
    })}\n`,
  };
}

function workflowRun(overrides = {}) {
  return {
    databaseId: 101,
    headBranch: tag,
    headSha,
    status: 'completed',
    conclusion: 'success',
    url: 'https://github.example.test/actions/runs/101',
    ...overrides,
  };
}

test('Git porcelain NUL parsing preserves filenames and rename source paths', () => {
  const parsed = parseGitStatus(` M ${generatedReport}\0?? reports/日本語 report.html\0R  reports/new.html\0reports/old.html\0`);
  assert.deepEqual(parsed, [
    { status: ' M', path: generatedReport },
    { status: '??', path: 'reports/日本語 report.html' },
    { status: 'R ', path: 'reports/new.html', oldPath: 'reports/old.html' },
  ]);
  assert.deepEqual(parseGitStatus(''), []);
});

test('only explicitly allowed generated paths can enter the daily commit', () => {
  assert.deepEqual(assertGeneratedChanges([{ status: ' M', path: generatedReport }]), [generatedReport]);
  assert.deepEqual(assertGeneratedChanges([{ status: '??', path: generatedReport }]), [generatedReport]);
  for (const unexpected of [
    '.env',
    'weak-early-beta-gate/.env',
    'scripts/windows/weak-early-beta-daily-runner.mjs',
    'weak_early_beta/fundamental_worker/out/historical-secret.json',
    'reports/weak_early_beta_historical_unrelated.html',
  ]) {
    assert.throws(() => assertGeneratedChanges([{ status: '??', path: unexpected }]), /unexpected|allow|generated/i, unexpected);
  }
});

test('staged files require the explicit staging audit and destructive changes are refused', () => {
  for (const status of ['M ', 'A ', 'MM']) {
    assert.throws(() => assertGeneratedChanges([{ status, path: generatedReport }]), /staged|index|unexpected/i);
  }
  assert.deepEqual(assertGeneratedChanges([{ status: 'M ', path: generatedReport }], { allowStaged: true }), [generatedReport]);
  for (const status of [' D', 'D ', 'R ', ' C', 'UU']) {
    assert.throws(() => assertGeneratedChanges([{ status, path: generatedReport, oldPath: 'reports/old.html' }], { allowStaged: true }));
  }
  assert.throws(() => assertGeneratedChanges([{ status: 'A ', path: '.env' }], { allowStaged: true }), /unexpected|allow|generated/i);
});

test('queue identities use signal date and symbol', () => {
  assert.deepEqual(queueIdentities([queueItem('1234'), queueItem('5678')]), [`${signalDate}|1234`, `${signalDate}|5678`]);
  assert.deepEqual(queueIdentities([]), []);
});

test('a two-item queue with one alert per child drains both and verifies each import', async () => {
  let queue = [queueItem('1234'), queueItem('5678')];
  let children = 0;
  const verified = [];
  const receipts = await drainFundamentalQueue({
    readQueue: async () => structuredClone(queue),
    runChild: async () => {
      children += 1;
      queue = queue.slice(1);
      return childReceipt();
    },
    verifyImported: async identities => {
      assert.equal(identities.length, 1);
      assert.ok(queue.every(item => !identities.includes(`${item.signal_date}|${item.symbol}`)));
      verified.push(...identities);
    },
  });
  assert.equal(children, 2);
  assert.deepEqual(verified, [`${signalDate}|1234`, `${signalDate}|5678`]);
  assert.equal(receipts.length, 2);
});

test('an empty queue creates no fundamental child', async () => {
  let children = 0;
  await drainFundamentalQueue({
    readQueue: async () => [],
    runChild: async () => { children += 1; throw new Error('unexpected child'); },
    verifyImported: async identities => assert.deepEqual(identities, []),
  });
  assert.equal(children, 0);
});

test('an unchanged queue stops after one child instead of retrying indefinitely', async () => {
  let children = 0;
  let verified = false;
  await assert.rejects(drainFundamentalQueue({
    readQueue: async () => [queueItem('1234')],
    runChild: async () => { children += 1; return childReceipt(); },
    verifyImported: async () => { verified = true; },
  }), /progress|unchanged|remaining/i);
  assert.equal(children, 1);
  assert.equal(verified, false);
});

test('failed child receipts stop the batch before another analysis or import verification', async () => {
  for (const failed of [childReceipt({ code: 1 }), childReceipt({ ok: false }), { code: 0, stdout: 'no receipt\n' }]) {
    let children = 0;
    let verified = false;
    await assert.rejects(drainFundamentalQueue({
      readQueue: async () => [queueItem('1234'), queueItem('5678')],
      runChild: async () => { children += 1; return failed; },
      verifyImported: async () => { verified = true; },
    }));
    assert.equal(children, 1);
    assert.equal(verified, false);
  }
});

test('new queue identities fail the bounded batch even when the queue shrinks', async () => {
  let children = 0;
  let queue = [queueItem('1234'), queueItem('5678')];
  await assert.rejects(drainFundamentalQueue({
    readQueue: async () => structuredClone(queue),
    runChild: async () => { children += 1; queue = [queueItem('9999')]; return childReceipt(); },
    verifyImported: async () => { throw new Error('unexpected import verification'); },
  }), /unexpected|new|initial|changed|progress/i);
  assert.equal(children, 1);
});

test('missing imported evidence rejects a drained queue', async () => {
  let queue = [queueItem('1234')];
  await assert.rejects(drainFundamentalQueue({
    readQueue: async () => structuredClone(queue),
    runChild: async () => { queue = []; return childReceipt(); },
    verifyImported: async () => { throw new Error('ledger has no matching analysis snapshot'); },
  }), /no matching analysis snapshot/);
});

test('queue progress must match the receipt count and HTML-only delivery', async () => {
  for (const invalidReceipt of [
    childReceipt({ imported: 2 }),
    childReceipt({ imported: 0 }),
    childReceipt({ imported: 0.5 }),
    { code: 0, stdout: JSON.stringify({ ok: true, imported: 1, posted: 1 }) },
  ]) {
    let queue = [queueItem('1234'), queueItem('5678')];
    let children = 0;
    await assert.rejects(drainFundamentalQueue({
      readQueue: async () => structuredClone(queue),
      runChild: async () => { children += 1; queue = queue.slice(1); return invalidReceipt; },
      verifyImported: async () => { throw new Error('unexpected verification'); },
    }), /progress|HTML-only import/i);
    assert.equal(children, 1);
  }
});

test('duplicate or malformed queue identities fail before a child starts', async () => {
  for (const queue of [[queueItem('1234'), queueItem('1234')], [queueItem('../secret')], [{ symbol: '1234' }]]) {
    await assert.rejects(drainFundamentalQueue({
      readQueue: async () => queue,
      runChild: async () => { throw new Error('child must not run'); },
      verifyImported: async () => {},
    }), /queue identity/i);
  }
});

function importedState() {
  const analysisCutoff = '2026-10-06T08:00:00.123Z';
  return {
    claims: {}, failed: {}, posted: {}, pendingLogEvents: [],
    completed: {
      [`weak-early-beta:${signalDate}:1234`]: {
        delivery: 'html', analysisBasis: 'analysis_start', analysisCutoff,
        report: { alertId: `weak-early-beta:${signalDate}:1234`, auditStatus: 'pass', signalDate, symbolCode: '1234', analysisCutoff },
      },
    },
  };
}

test('HTML import verification requires finalized state and the audited cutoff snapshot', () => {
  const identities = [`${signalDate}|1234`];
  assert.doesNotThrow(() => assertHtmlImports(importedState(), identities));
  const mutations = [
    state => { state.claims.active = {}; },
    state => { state.failed.active = {}; },
    state => { state.pendingLogEvents.push('pending'); },
    state => { state.completed = {}; },
    state => { state.completed[`weak-early-beta:${signalDate}:1234`].delivery = 'discord'; },
    state => { state.completed[`weak-early-beta:${signalDate}:1234`].analysisBasis = 'historical_signal'; },
    state => { state.completed[`weak-early-beta:${signalDate}:1234`].report.auditStatus = 'fail'; },
    state => { state.completed[`weak-early-beta:${signalDate}:1234`].report.signalDate = '2026-10-05'; },
    state => { state.completed[`weak-early-beta:${signalDate}:1234`].report.symbolCode = '5678'; },
    state => {
      delete state.completed[`weak-early-beta:${signalDate}:1234`].analysisCutoff;
      delete state.completed[`weak-early-beta:${signalDate}:1234`].report.analysisCutoff;
    },
    state => {
      state.completed[`weak-early-beta:${signalDate}:1234`].analysisCutoff = 'invalid date';
      state.completed[`weak-early-beta:${signalDate}:1234`].report.analysisCutoff = 'invalid date';
    },
    state => { state.completed[`weak-early-beta:${signalDate}:1234`].report.analysisCutoff = '2026-10-06T08:00:00.124Z'; },
  ];
  for (const mutate of mutations) {
    const state = importedState();
    mutate(state);
    assert.throws(() => assertHtmlImports(state, identities), /incomplete|missing verified HTML import/i);
  }
});

function validatedOutputFixture({ note = 'company-specific analysis', bom = false } = {}) {
  const state = importedState();
  const saved = state.completed[`weak-early-beta:${signalDate}:1234`];
  saved.report.fields = [{ name: 'ファンダ要点', value: note }];
  const raw = Buffer.from(`${bom ? '\uFEFF' : ''}${JSON.stringify({ reports: [saved.report] })}`, 'utf8');
  const receipt = { validatedReportSha256: createHash('sha256').update(raw).digest('hex'), imported: 1 };
  return { raw, state, receipt, env: {} };
}

test('fundamental output requires the validated SHA and exact imported snapshot content', () => {
  assert.doesNotThrow(() => assertValidatedFundamentalOutput(validatedOutputFixture()));
  assert.doesNotThrow(() => assertValidatedFundamentalOutput(validatedOutputFixture({ bom: true })));
  const changedRaw = validatedOutputFixture();
  changedRaw.raw = Buffer.from(`${changedRaw.raw}\n`, 'utf8');
  assert.throws(() => assertValidatedFundamentalOutput(changedRaw), /differs from the validated local report receipt/);
  for (const hash of [undefined, 'a'.repeat(63), 'A'.repeat(64), 'f'.repeat(64)]) {
    const fixture = validatedOutputFixture();
    fixture.receipt.validatedReportSha256 = hash;
    assert.throws(() => assertValidatedFundamentalOutput(fixture), /validated local report receipt/);
  }
  const changedSnapshot = validatedOutputFixture();
  changedSnapshot.state.completed[`weak-early-beta:${signalDate}:1234`].report.fields[0].value = 'different imported analysis';
  assert.throws(() => assertValidatedFundamentalOutput(changedSnapshot), /differs from the imported HTML snapshot/);
  const missingSnapshot = validatedOutputFixture();
  missingSnapshot.state.completed = {};
  assert.throws(() => assertValidatedFundamentalOutput(missingSnapshot), /differs from the imported HTML snapshot/);
});

test('fundamental output count must equal the imported receipt', () => {
  for (const imported of [0, 2]) {
    const fixture = validatedOutputFixture();
    fixture.receipt.imported = imported;
    assert.throws(() => assertValidatedFundamentalOutput(fixture), /report count differs from imported receipt/);
  }
  const fixture = validatedOutputFixture();
  fixture.raw = Buffer.from(JSON.stringify({ reports: {} }));
  fixture.receipt.validatedReportSha256 = createHash('sha256').update(fixture.raw).digest('hex');
  assert.throws(() => assertValidatedFundamentalOutput(fixture), /report count differs from imported receipt/);
});

test('configured secret values are refused in both plain and JSON escaped output', () => {
  const secret = 'synthetic-secret-123456789';
  for (const key of ['DISCORD_TOKEN', 'SESSION_SECRET', 'PASSWORD', 'API_KEY', 'PRIVATE_KEY', 'CREDENTIAL_FILE', 'WEBHOOK_URL']) {
    const fixture = validatedOutputFixture({ note: `analysis ${secret}` });
    fixture.env = { [key]: secret };
    assert.throws(() => assertValidatedFundamentalOutput(fixture), /contains a configured secret/);
  }
  const escapedSecret = 'synthetic-"secret"\\value\n123456789';
  const escaped = validatedOutputFixture({ note: escapedSecret });
  escaped.env = { discordToken: escapedSecret };
  assert.equal(escaped.raw.toString('utf8').includes(escapedSecret), false);
  assert.throws(() => assertValidatedFundamentalOutput(escaped), /contains a configured secret/);
  const ordinaryValue = '/synthetic/public/report/path';
  const ordinary = validatedOutputFixture({ note: ordinaryValue });
  ordinary.env = { PUBLIC_REPORT_PATH: ordinaryValue };
  assert.doesNotThrow(() => assertValidatedFundamentalOutput(ordinary));
});

function mockedGit({ initial = ` M ${generatedReport}\0`, staged = `${generatedReport}\0`, afterStage = `M  ${generatedReport}\0`, afterCommit = '', normalized = `${generatedReport}\0` } = {}) {
  const calls = [];
  let statusReads = 0;
  return {
    calls,
    git: async args => {
      calls.push(args);
      let stdout = '';
      if (args[0] === 'status') stdout = [initial, afterStage, afterCommit][statusReads++];
      if (args[0] === 'diff') stdout = args.includes('--cached') ? staged : normalized;
      return { stdout };
    },
  };
}

test('generated commits stage exact leaves and push only the Cloud research branch', async () => {
  const mock = mockedGit();
  const message = 'chore: refresh Cloud beta test';
  const result = await commitGeneratedChanges({ git: mock.git, message });
  assert.deepEqual(result, { committed: true, paths: [generatedReport] });
  assert.deepEqual(mock.calls, [
    ['status', '--porcelain=v1', '-z', '--untracked-files=all'],
    ['diff', '--name-only', '-z', '--', generatedReport],
    ['add', '--', generatedReport],
    ['diff', '--cached', '--name-only', '-z'],
    ['status', '--porcelain=v1', '-z', '--untracked-files=all'],
    ['commit', '-m', message],
    ['status', '--porcelain=v1', '-z', '--untracked-files=all'],
    ['push', 'origin', 'HEAD:refs/heads/research/weak-early-beta'],
  ]);
});

test('a clean generated set does not create an empty commit or push', async () => {
  const mock = mockedGit({ initial: '' });
  assert.deepEqual(await commitGeneratedChanges({ git: mock.git, message: 'unused' }), { committed: false, paths: [] });
  assert.equal(mock.calls.length, 1);
});

test('unexpected staging and status races stop before commit or push', async () => {
  for (const fixture of [
    { initial: `M  ${generatedReport}\0` },
    { initial: '?? .env\0' },
    { staged: `${generatedReport}\0.env\0` },
    { afterStage: `M  ${generatedReport}\0?? .env\0` },
    { afterStage: `MM ${generatedReport}\0` },
    { afterStage: '' },
  ]) {
    const mock = mockedGit(fixture);
    await assert.rejects(commitGeneratedChanges({ git: mock.git, message: 'must not commit' }));
    assert.equal(mock.calls.some(args => ['commit', 'push', 'tag'].includes(args[0])), false);
  }
});

test('a change during commit stops the subsequent push', async () => {
  const mock = mockedGit({ afterCommit: ` M ${generatedReport}\0` });
  await assert.rejects(commitGeneratedChanges({ git: mock.git, message: 'test commit' }), /changed.*commit|refusing push/i);
  assert.equal(mock.calls.some(args => args[0] === 'commit'), true);
  assert.equal(mock.calls.some(args => args[0] === 'push'), false);
});

test('deployment HEAD must equal the exact current Cloud research remote ref', async () => {
  const calls = [];
  const git = async args => {
    calls.push(args);
    return { stdout: args[0] === 'rev-parse' ? `${headSha}\n` : `${headSha}\trefs/heads/research/weak-early-beta\n` };
  };
  assert.equal(await requireRemoteHead(git), headSha);
  assert.deepEqual(calls, [
    ['rev-parse', 'HEAD'],
    ['ls-remote', '--exit-code', 'origin', 'refs/heads/research/weak-early-beta'],
  ]);
  for (const remote of [
    `${'b'.repeat(40)}\trefs/heads/research/weak-early-beta\n`,
    `${headSha}\trefs/heads/main\n`,
    '',
  ]) {
    await assert.rejects(requireRemoteHead(async args => ({ stdout: args[0] === 'rev-parse' ? `${headSha}\n` : remote })), /latest origin/i);
  }
});

test('workflow selection requires the exact deployment tag and commit', () => {
  const exact = workflowRun();
  const unrelated = [workflowRun({ headBranch: 'cloud-deploy-old' }), workflowRun({ headSha: 'b'.repeat(40) })];
  assert.equal(selectWorkflowRun(unrelated, { tag, headSha }), null);
  assert.deepEqual(selectWorkflowRun([...unrelated, exact], { tag, headSha }), exact);
  assert.throws(() => selectWorkflowRun([exact, workflowRun({ databaseId: 102 })], { tag, headSha }), /ambiguous|multiple/i);
});

test('tag workflow waiting ignores unrelated successes and waits for the matching run', async () => {
  const waits = [];
  let elapsed = 0;
  let polls = 0;
  const exact = workflowRun();
  const result = await waitForTagWorkflow({
    tag, headSha, timeoutMs: 180_000, pollMs: 30_000,
    now: () => elapsed,
    wait: async ms => { waits.push(ms); elapsed += ms; },
    listRuns: async () => {
      polls += 1;
      const unrelated = workflowRun({ headBranch: 'cloud-deploy-old' });
      if (polls === 1) return [unrelated];
      return [unrelated, polls === 2 ? workflowRun({ status: 'in_progress', conclusion: null }) : exact];
    },
  });
  assert.deepEqual(result, exact);
  assert.equal(polls, 3);
  assert.ok(waits.every(ms => ms > 0 && ms <= 60_000));
});

test('deployment timeout is bounded even with a poll interval longer than one minute', async () => {
  const waits = [];
  let elapsed = 0;
  let polls = 0;
  await assert.rejects(waitForTagWorkflow({
    tag, headSha, timeoutMs: 125_000, pollMs: 300_000,
    now: () => elapsed,
    wait: async ms => { waits.push(ms); elapsed += ms; },
    listRuns: async () => { polls += 1; return [workflowRun({ headSha: 'b'.repeat(40) })]; },
  }), /timeout|timed out/i);
  assert.ok(elapsed <= 125_000, `elapsed=${elapsed}`);
  assert.ok(polls <= 5, `polls=${polls}`);
  assert.ok(waits.length > 0);
  assert.ok(waits.every(ms => ms > 0 && ms <= 60_000));
});

test('completed deployment failures stop polling immediately', async () => {
  for (const conclusion of ['failure', 'cancelled', 'timed_out', 'skipped']) {
    let waits = 0;
    await assert.rejects(waitForTagWorkflow({
      tag, headSha, timeoutMs: 90_000,
      now: () => 0,
      wait: async () => { waits += 1; },
      listRuns: async () => [workflowRun({ conclusion })],
    }), /fail|conclusion|cancel|timed|skipped/i);
    assert.equal(waits, 0);
  }
});

function notificationReceipt({ signal = 2, completion = 1, dryRun = true, date = signalDate } = {}) {
  return { date, signal_notifications: signal, completion_notifications: completion, dry_run: dryRun };
}

test('notification reconciliation sends the exact preview counts and confirms zero remaining', async () => {
  const calls = [];
  const progress = [];
  const initial = notificationReceipt();
  const actual = notificationReceipt({ dryRun: false });
  const remaining = notificationReceipt({ signal: 0, completion: 0 });
  const result = await reconcileNotifications({
    date: signalDate,
    preview: async phase => { calls.push(phase); return phase === 'preview' ? initial : remaining; },
    send: async () => { calls.push('send'); return actual; },
    onProgress: async event => { progress.push(event); },
  });
  assert.deepEqual(calls, ['preview', 'send', 'reconcile']);
  assert.deepEqual(result, { preview: initial, notifications: actual, remaining });
  assert.equal(progress.length, 3);
  assert.deepEqual(progress.map(item => item.phase), ['preview', 'sent', 'reconcile']);
  assert.deepEqual(progress.map(item => item.receipt), [initial, actual, remaining]);
});

test('zero preview notifications skip send and still reconcile the remaining queue', async () => {
  const calls = [];
  const progress = [];
  let sends = 0;
  const empty = notificationReceipt({ signal: 0, completion: 0 });
  const result = await reconcileNotifications({
    date: signalDate,
    preview: async phase => { calls.push(phase); return empty; },
    send: async () => { sends += 1; throw new Error('zero preview must not send'); },
    onProgress: async event => { progress.push(event); },
  });
  assert.equal(sends, 0);
  assert.deepEqual(calls, ['preview', 'reconcile']);
  assert.deepEqual(result.notifications, {
    date: signalDate, signal_notifications: 0, completion_notifications: 0,
    dry_run: false, skipped: 'no_new_symbols',
  });
  assert.deepEqual(result.remaining, empty);
  assert.deepEqual(progress.map(item => item.phase), ['preview', 'sent', 'reconcile']);
  assert.deepEqual(progress[1].receipt, result.notifications);
});

test('notification count mismatches stop without retrying the actual send', async () => {
  for (const actual of [
    notificationReceipt({ signal: 1, dryRun: false }),
    notificationReceipt({ signal: 3, dryRun: false }),
    notificationReceipt({ completion: 0, dryRun: false }),
  ]) {
    let sends = 0;
    let previews = 0;
    await assert.rejects(reconcileNotifications({
      date: signalDate,
      preview: async () => { previews += 1; return notificationReceipt(); },
      send: async () => { sends += 1; return actual; },
    }), /count|match|receipt|reconcil/i);
    assert.equal(sends, 1);
    assert.equal(previews, 1);
  }
});

test('remaining notification work rejects completion and never triggers another send', async () => {
  let sends = 0;
  const calls = [];
  await assert.rejects(reconcileNotifications({
    date: signalDate,
    preview: async phase => { calls.push(phase); return notificationReceipt({ signal: phase === 'preview' ? 2 : 1, completion: phase === 'preview' ? 1 : 0 }); },
    send: async () => { sends += 1; return notificationReceipt({ dryRun: false }); },
  }), /remain|pending|reconcil|incomplete/i);
  assert.equal(sends, 1);
  assert.deepEqual(calls, ['preview', 'reconcile']);
});

test('invalid notification previews stop before an actual send', async () => {
  const invalid = [
    notificationReceipt({ date: '2026-10-05' }),
    notificationReceipt({ signal: -1 }),
    notificationReceipt({ signal: 0.5 }),
    notificationReceipt({ signal: '2' }),
    notificationReceipt({ completion: -1 }),
    notificationReceipt({ completion: Number.NaN }),
    notificationReceipt({ dryRun: false }),
    { date: signalDate, signal_notifications: 2, completion_notifications: 1 },
  ];
  for (const receipt of invalid) {
    let sends = 0;
    await assert.rejects(reconcileNotifications({
      date: signalDate,
      preview: async () => receipt,
      send: async () => { sends += 1; throw new Error('invalid preview must not send'); },
    }));
    assert.equal(sends, 0);
  }
});

test('invalid actual notification receipts stop without another preview or send', async () => {
  for (const receipt of [
    notificationReceipt({ date: '2026-10-05', dryRun: false }),
    notificationReceipt({ signal: -1, dryRun: false }),
    notificationReceipt({ completion: 0.5, dryRun: false }),
    notificationReceipt({ dryRun: true }),
    { date: signalDate, signal_notifications: 2, completion_notifications: 1 },
  ]) {
    let sends = 0;
    let previews = 0;
    await assert.rejects(reconcileNotifications({
      date: signalDate,
      preview: async () => { previews += 1; return notificationReceipt(); },
      send: async () => { sends += 1; return receipt; },
    }));
    assert.equal(sends, 1);
    assert.equal(previews, 1);
  }
});

test('invalid final notification receipts retain one-send behavior and reject completion', async () => {
  for (const invalid of [
    notificationReceipt({ signal: 0, completion: 0, date: '2026-10-05' }),
    notificationReceipt({ signal: -1, completion: 0 }),
    notificationReceipt({ signal: 0, completion: 0, dryRun: false }),
  ]) {
    let sends = 0;
    await assert.rejects(reconcileNotifications({
      date: signalDate,
      preview: async phase => phase === 'preview' ? notificationReceipt() : invalid,
      send: async () => { sends += 1; return notificationReceipt({ dryRun: false }); },
    }));
    assert.equal(sends, 1);
  }
});

test('live verification checks health then a manual OAuth redirect without login cookies', async () => {
  for (const location of [
    'https://discord.com/oauth2/authorize?client_id=test&response_type=code',
    `${origin}/auth/login`,
    '/auth/login',
  ]) {
    const requests = [];
    await verifyLiveWorker({ origin, fetchImpl: async (url, options) => {
      requests.push({ url: String(url), options });
      return new URL(url).pathname === '/healthz'
        ? new Response('ok', { status: 200 })
        : new Response(null, { status: 302, headers: { location } });
    } });
    assert.deepEqual(requests.map(request => new URL(request.url).pathname), ['/healthz', '/']);
    assert.equal(requests[1].options.redirect, 'manual');
    assert.equal(requests[1].options.headers?.cookie, undefined);
  }
});

test('live verification rejects unhealthy, public, or unexpected authentication responses', async () => {
  for (const [health, root] of [
    [new Response('error', { status: 503 }), new Response(null, { status: 302, headers: { location: '/auth/login' } })],
    [new Response('unrelated page', { status: 200 }), new Response(null, { status: 302, headers: { location: '/auth/login' } })],
    [new Response('ok', { status: 200 }), new Response('<html>public report</html>', { status: 200 })],
    [new Response('ok', { status: 200 }), new Response(null, { status: 302, headers: { location: 'https://evil.example.test/auth/login' } })],
    [new Response('ok', { status: 200 }), new Response(null, { status: 302, headers: { location: 'https://discord.com/channels/test' } })],
    [new Response('ok', { status: 200 }), new Response(null, { status: 302 })],
  ]) {
    await assert.rejects(verifyLiveWorker({
      origin,
      fetchImpl: async url => new URL(url).pathname === '/healthz' ? health : root,
    }));
  }
});

test('live verification refuses other origins before any request', async () => {
  await assert.rejects(verifyLiveWorker({
    origin: 'https://other-worker.example.test',
    fetchImpl: async () => { throw new Error('must not fetch another worker'); },
  }), /unexpected live Cloud origin/);
});

test('npm uses the configured node and npm CLI on Windows and defaults to check', () => {
  const parent = path.resolve(os.tmpdir());
  const fixture = fs.mkdtempSync(path.join(parent, 'weak-early-beta-npm invocation-'));
  try {
    const npmPath = path.join(fixture, 'npm.cmd');
    const npmCli = path.join(fixture, 'node_modules', 'npm', 'bin', 'npm-cli.js');
    const nodePath = path.join(fixture, 'node.exe');
    fs.mkdirSync(path.dirname(npmCli), { recursive: true });
    fs.writeFileSync(npmCli, '');
    assert.deepEqual(npmInvocation({ npmPath, nodePath }, undefined, 'win32'), { exe: nodePath, args: [npmCli, 'run', 'check'] });
    assert.deepEqual(npmInvocation({ npmPath: '/usr/bin/npm' }, 'check', 'linux'), { exe: '/usr/bin/npm', args: ['run', 'check'] });
    fs.rmSync(npmCli);
    assert.throws(() => npmInvocation({ npmPath, nodePath }, 'check', 'win32'), /npm CLI not found/i);
  } finally {
    const resolved = path.resolve(fixture);
    if (!resolved.startsWith(`${parent}${path.sep}`) || !path.basename(resolved).startsWith('weak-early-beta-npm invocation-')) {
      throw new Error('refusing to remove an unexpected fixture path');
    }
    fs.rmSync(resolved, { recursive: true, force: true });
  }
});


test('normalized no-op does not create a commit and still requires a clean worktree', async () => {
  const mock = mockedGit({ normalized: '', staged: '', afterStage: '' });
  assert.deepEqual(await commitGeneratedChanges({ git: mock.git, message: 'unused' }), { committed: false, paths: [] });
  assert.equal(mock.calls.some(args => ['commit', 'push'].includes(args[0])), false);
  const race = mockedGit({ normalized: '', staged: '', afterStage: ` M ${generatedReport}\0` });
  await assert.rejects(commitGeneratedChanges({ git: race.git, message: 'unused' }), /working\/staged.*staging/);
});

test('unexpected normalized names stop before staging', async () => {
  const mock = mockedGit({ normalized: `${generatedReport}\0.env\0` });
  await assert.rejects(commitGeneratedChanges({ git: mock.git, message: 'unused' }), /normalized generated diff/);
  assert.equal(mock.calls.some(args => ['add', 'commit', 'push'].includes(args[0])), false);
});

test('real Git autocrlf normalization commits only substantive generated changes', async () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'cloud-normalized-git-'));
  const csv = 'weak_early_beta/state/metrics.csv';
  const calls = [];
  function execute(args) {
    const output = spawnSync('git', args, { cwd: root, encoding: 'utf8' });
    assert.equal(output.status, 0, output.stderr);
    return { stdout: output.stdout };
  }
  const git = async args => {
    calls.push(args);
    return args[0] === 'push' ? { stdout: '' } : execute(args);
  };
  try {
    execute(['init', '-b', 'research/weak-early-beta']);
    execute(['config', 'user.name', 'Cloud test']);
    execute(['config', 'user.email', 'cloud-test@example.invalid']);
    execute(['config', 'core.autocrlf', 'true']);
    for (const file of [csv, generatedReport, 'unrelated.txt']) {
      fs.mkdirSync(path.dirname(path.join(root, file)), { recursive: true });
      fs.writeFileSync(path.join(root, file), 'before\r\n');
    }
    execute(['add', '--', csv, generatedReport, 'unrelated.txt']);
    execute(['commit', '-m', 'test baseline']);
    fs.writeFileSync(path.join(root, csv), 'before\n');
    fs.writeFileSync(path.join(root, generatedReport), 'after\n');
    assert.deepEqual(await commitGeneratedChanges({ git, message: 'test generated report' }), { committed: true, paths: [generatedReport] });
    assert.deepEqual(execute(['diff-tree', '--no-commit-id', '--name-only', '-r', 'HEAD']).stdout.trim().split('\n'), [generatedReport]);
    assert.equal(execute(['status', '--porcelain']).stdout, '');
    assert.deepEqual(new Set(calls.find(args => args[0] === 'add').slice(2)), new Set([generatedReport, csv]));
    assert.deepEqual(calls.at(-1), ['push', 'origin', 'HEAD:refs/heads/research/weak-early-beta']);
  } finally { fs.rmSync(root, { recursive: true, force: true }); }
});
