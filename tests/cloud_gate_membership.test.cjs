const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { webcrypto } = require('node:crypto');

const repoRoot = path.resolve(__dirname, '..');
const tsPath = [
  'weak-early-beta-gate/node_modules/typescript/lib/typescript.js',
  'report-gate/node_modules/typescript/lib/typescript.js',
].map((relative) => path.join(repoRoot, relative)).find((candidate) => fs.existsSync(candidate));
assert.ok(tsPath, 'Install one gate package before running the membership tests.');
const ts = require(tsPath);

// Load the actual Worker modules with synthetic credentials and no network.
// Only relative imports under the Cloud source directory are permitted.
function createModules({ fetchMock, clock, researchSnapshotReader } = {}) {
  const sourceRoot = path.join(repoRoot, 'weak-early-beta-gate', 'src');
  const cache = new Map();
  function load(name, parent = sourceRoot) {
    const filename = path.resolve(parent, `${name.replace(/\.ts$/, '')}.ts`);
    assert.ok(filename.startsWith(`${sourceRoot}${path.sep}`), 'Test imports must remain inside the Cloud gate.');
    if (cache.has(filename)) return cache.get(filename).exports;
    const module = { exports: {} };
    cache.set(filename, module);
    // Authorization tests replace only the data adapter seam. Actual source
    // gate/role/renderer code still runs; canonical D1/hash validation has its
    // own migration suite. Never load the real price snapshot in these tests.
    if (path.basename(filename) === 'new-a-data.ts' && researchSnapshotReader) {
      module.exports = { readResearchASnapshot: researchSnapshotReader };
      return module.exports;
    }
    let source = fs.readFileSync(filename, 'utf8');
    if (path.basename(filename) === 'shared-report-gate.ts') source += '\nexport const __test = { createSession };';
    const compiled = ts.transpileModule(source, {
      compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS },
    }).outputText;
    const sandbox = {
      exports: module.exports, module,
      require: (specifier) => {
        if (specifier === 'cloudflare:workers') return require('./helpers/cloud-role-authority.cjs').runtime;
        assert.ok(specifier.startsWith('.'), `Unexpected dependency: ${specifier}`);
        return load(specifier, path.dirname(filename));
      },
      Request, Response, Headers, URL, URLSearchParams, AbortSignal,
      TextEncoder, TextDecoder, Uint8Array, crypto: webcrypto, atob, btoa,
      fetch: fetchMock || (() => { throw new Error('Network access is forbidden in membership tests.'); }),
      Date: class extends Date {
        constructor(...args) { super(...(args.length ? args : [clock ? clock.now : Date.now()])); }
        static now() { return clock ? clock.now : Date.now(); }
      },
      console: { error() {}, log() {}, warn() {} },
      setTimeout, clearTimeout,
    };
    vm.runInNewContext(compiled, sandbox, { filename });
    return module.exports;
  }
  return { load };
}

// Convert VM objects to the host realm before structural assertions.
const plain = (value) => JSON.parse(JSON.stringify(value));

const rules = createModules().load('./cloud-membership');
const NOW = Date.parse('2026-10-02T07:00:00.000Z');

function preferences(overrides = {}) {
  // Explicit fixture choices retain the boundary tests' original 1,000/D5 case.
  return { ...plain(rules.DEFAULT_PREFERENCES), max_price: 1000, exit_endpoint: 'd5_close', ...overrides,
    notifications: { ...plain(rules.DEFAULT_PREFERENCES.notifications), ...(overrides.notifications || {}) } };
}

function memberFixture() {
  return {
    link: {
      member_id: 'internal-member-1', discord_user_id: 'discord-user-1',
      whop_user_id: 'user_1', membership_id: 'mem_1', payment_id: 'pay_1',
      environment: 'live', verified_at: '2026-09-01T00:00:00Z',
      verification_method: 'dual_oauth', evidence_reference: 'verified-link-receipt-1', revoked_at: null,
    },
    policy: { account_id: 'biz_1', product_ids: ['prod_1'], paid_plan_ids: ['plan_1'], one_time_plan_ids: [] },
    membership: {
      id: 'mem_1', user_id: 'user_1', account: { id: 'biz_1' }, product_id: 'prod_1', plan_id: 'plan_1',
      status: 'active', current_period_start: '2026-10-01T00:00:00Z', current_period_end: '2026-11-01T00:00:00Z',
      cancel_at_period_end: false, canceled_at: null,
    },
    payment: {
      id: 'pay_1', membership_id: 'mem_1', account_id: 'biz_1', user: { id: 'user_1' },
      status: 'paid', total: { amount: '1000', currency: 'jpy' },
      refunded_amount: { amount: '0', currency: 'jpy' }, paid_at: '2026-10-01T00:00:00Z',
    },
  };
}

function membershipDecision(fixture = memberFixture(), now = NOW) {
  return rules.evaluateMembership(fixture.membership, fixture.payment, fixture.link, fixture.policy, now);
}

function eventFixture(overrides = {}) {
  return {
    signal_id: 'signal-private-1', kind: 'new_detection', detection_date: '2026-09-24',
    adapter_version: 'cloud-ledger-v1', source_ledger_revision: 'a'.repeat(64),
    signal_actual_close: 1000, signal_price_status: 'verified',
    endpoints: {
      d5_close: { date: '2026-10-01', actual_price: 1100, status: 'verified',
        fetched_at: '2026-10-01T07:00:00Z', source: 'b'.repeat(64) },
      d6_open: { date: '2026-10-02', actual_price: 1110, status: 'verified',
        fetched_at: '2026-10-02T00:01:00Z', source: 'c'.repeat(64) },
    },
    ...overrides,
  };
}

function notificationDecision(event = eventFixture(), prefs = preferences({ notifications: { new_detection: true } }),
  member, now = NOW) {
  const currentMembership = member || { ...membershipDecision(), checked_at: new Date(now).toISOString() };
  return rules.evaluateNotification(event, prefs, currentMembership, now);
}

test('both notifications default OFF and preference storage collects no email address', () => {
  assert.deepEqual(plain(rules.DEFAULT_PREFERENCES), {
    max_price: 1000, exit_endpoint: 'd6_open', base_shares: 100, cost_percent: 0,
    notifications: { new_detection: false, reminder: false },
  });
  assert.throws(() => rules.validatePreferences({ ...preferences(), email: 'unused@example.invalid' }), /invalid_preferences/);
});

for (const max_price of [1000, 3000, 5000, null, 1250.25]) {
  for (const exit_endpoint of ['d5_close', 'd6_open']) {
    test(`preferences accept ${max_price ?? 'unlimited'} and ${exit_endpoint}`, () => {
      const input = preferences({ max_price, exit_endpoint, notifications: { reminder: true } });
      assert.deepEqual(plain(rules.validatePreferences(input)), input);
    });
  }
}

for (const max_price of [undefined, '', '1000', 0, -1, NaN, Infinity, 1.001, 1.2300000001, 1e-7]) {
  test(`preferences reject unsafe price boundary ${String(max_price)}`, () => {
    assert.throws(() => rules.validatePreferences(preferences({ max_price })), /invalid_max_price/);
  });
}

test('preferences reject partial, mistyped, and unexpected notification settings', () => {
  for (const input of [null, [], {}, { ...preferences(), exit_endpoint: 'd6_close' },
    { ...preferences(), notifications: {} },
    { ...preferences(), notifications: { new_detection: false, reminder: 'true', result: false } },
    { ...preferences(), notifications: { ...preferences().notifications, email: true } }]) {
    assert.throws(() => rules.validatePreferences(input), /invalid_/);
  }
});

test('validated preferences do not share mutable notification state with request data', () => {
  const input = preferences({ notifications: { new_detection: true } });
  const validated = rules.validatePreferences(input);
  input.notifications.new_detection = false;
  assert.equal(validated.notifications.new_detection, true);
  assert.equal('result' in rules.DEFAULT_PREFERENCES.notifications, false);
});

test('a verified live paid member passes and its check time is generated by the server', () => {
  assert.deepEqual(plain(membershipDecision()), {
    status: 'paid', reason: 'verified_paid_membership', checked_at: '2026-10-02T07:00:00.000Z',
  });
});

test('scheduled cancellation retains access until the paid period ends', () => {
  const fixture = memberFixture();
  fixture.membership.cancel_at_period_end = true;
  fixture.membership.canceled_at = '2026-10-02T01:00:00Z';
  assert.equal(membershipDecision(fixture).status, 'paid');
  assert.equal(membershipDecision(fixture, Date.parse('2026-11-01T00:00:00Z')).status, 'free');
});

for (const status of ['canceled', 'expired', 'past_due', 'trialing', 'unpaid', 'unknown', 'completed']) {
  test(`membership status ${status} does not grant subscription access`, () => {
    const fixture = memberFixture();
    fixture.membership.status = status;
    assert.equal(membershipDecision(fixture).status, 'free');
  });
}

test('a completed purchase is accepted only when its plan explicitly permits one-time access', () => {
  const fixture = memberFixture();
  fixture.membership.status = 'completed';
  fixture.membership.current_period_end = null;
  fixture.membership.current_period_start = null;
  assert.notEqual(membershipDecision(fixture).status, 'paid');
  fixture.policy.one_time_plan_ids.push('plan_1');
  assert.equal(membershipDecision(fixture).status, 'paid');
});

for (const [label, change] of [
  ['test account', f => { f.link.environment = 'test'; }],
  ['revoked identity link', f => { f.link.revoked_at = '2026-10-01T00:00:00Z'; }],
  ['email-only linkage', f => { f.link.verification_method = 'email_match'; }],
  ['missing evidence', f => { f.link.evidence_reference = ''; }],
  ['missing verification time', f => { f.link.verified_at = ''; }],
  ['future verification time', f => { f.link.verified_at = '2027-01-01T00:00:00Z'; }],
  ['different membership', f => { f.membership.id = 'mem_other'; }],
  ['different owner', f => { f.membership.user_id = 'user_other'; }],
  ['different account', f => { f.membership.account.id = 'biz_other'; }],
  ['different product', f => { f.membership.product_id = 'prod_other'; }],
  ['free plan', f => { f.membership.plan_id = 'plan_free'; }],
  ['different payment', f => { f.payment.id = 'pay_other'; }],
  ['payment from another membership', f => { f.payment.membership_id = 'mem_other'; }],
  ['payment from another account', f => { f.payment.account_id = 'biz_other'; }],
  ['payment by another owner', f => { f.payment.user.id = 'user_other'; }],
  ['payment not completed', f => { f.payment.status = 'pending'; }],
  ['zero-price grant', f => { f.payment.total.amount = '0'; }],
  ['fully refunded payment', f => { f.payment.refunded_amount.amount = '1000'; }],
  ['negative refund', f => { f.payment.refunded_amount.amount = '-1'; }],
  ['currency mismatch', f => { f.payment.refunded_amount.currency = 'usd'; }],
  ['previous-period payment', f => { f.payment.paid_at = '2026-09-01T00:00:00Z'; }],
  ['future payment', f => { f.payment.paid_at = '2027-01-01T00:00:00Z'; }],
  ['unparseable payment timestamp', f => { f.payment.paid_at = 'unknown'; }],
  ['future period start', f => { f.membership.current_period_start = '2027-01-01T00:00:00Z'; }],
  ['missing subscription expiry', f => { f.membership.current_period_end = null; }],
  ['unparseable subscription expiry', f => { f.membership.current_period_end = 'unknown'; }],
]) {
  test(`${label} cannot grant paid access`, () => {
    const fixture = memberFixture();
    change(fixture);
    assert.notEqual(membershipDecision(fixture).status, 'paid');
  });
}

test('missing or malformed provider results fail closed', () => {
  for (const invalid of [undefined, null, [], 'failure']) {
    const fixture = memberFixture();
    fixture.membership = invalid;
    assert.equal(membershipDecision(fixture).status, 'unavailable');
    const paymentFixture = memberFixture();
    paymentFixture.payment = invalid;
    assert.equal(membershipDecision(paymentFixture).status, 'unavailable');
  }
});

for (const kind of ['new_detection', 'reminder']) {
  test(`${kind} stays suppressed until that individual notification is enabled`, () => {
    const event = eventFixture({ kind });
    assert.equal(notificationDecision(event, preferences()).reason, 'notification_off');
    for (const enabled of ['new_detection', 'reminder'].filter(k => k !== kind)) {
      assert.equal(notificationDecision(event, preferences({ notifications: { [enabled]: true } })).reason, 'notification_off');
    }
  });
}

for (const status of ['free', 'unverified', 'unavailable']) {
  test(`notification for ${status} membership is held even with opt-in`, () => {
    const decision = notificationDecision(undefined, undefined, { status, reason: `test_${status}`, checked_at: new Date(NOW).toISOString() });
    assert.equal(decision.status, 'held');
    assert.equal(decision.message, null);
  });
}

test('confirmed detection-day actual close uses an inclusive price cap', () => {
  for (const signal_actual_close of [999.99, 1000]) {
    assert.equal(notificationDecision(eventFixture({ signal_actual_close })).status, 'would_send');
  }
  assert.equal(notificationDecision(eventFixture({ signal_actual_close: 1000.01 })).reason, 'over_price_limit');
});

test('a finite cap holds unknown, zero, nonfinite, and unverified detection prices', () => {
  for (const signal_actual_close of [null, 0, -1, NaN, Infinity, '1000']) {
    assert.equal(notificationDecision(eventFixture({ signal_actual_close })).reason, 'signal_price_unverified');
  }
  for (const signal_price_status of ['pending', 'adjusted_reference', '', 'missing']) {
    assert.equal(notificationDecision(eventFixture({ signal_price_status })).reason, 'signal_price_unverified');
  }
});

test('unlimited selection does not turn an unknown detection price into a numeric substitute', () => {
  const event = eventFixture({ signal_actual_close: null, signal_price_status: 'pending' });
  const decision = notificationDecision(event, preferences({ max_price: null, notifications: { new_detection: true } }));
  assert.equal(decision.status, 'would_send');
  assert.equal(event.signal_actual_close, null);
  assert.equal(event.signal_price_status, 'pending');
});

test('2022 rows cannot produce notifications under any configured price limit', () => {
  for (const max_price of [1000, null]) {
    const decision = notificationDecision(eventFixture({ detection_date: '2022-12-30', kind: 'new_detection' }),
      preferences({ max_price, notifications: { new_detection: true } }));
    assert.equal(decision.status, 'suppressed');
    assert.equal(decision.reason, 'excluded_research_year');
  }
});

for (const exit_endpoint of ['d5_close', 'd6_open']) {
  test(`${exit_endpoint} at 08:00 JST creates a reminder while its result remains pending`, () => {
    const event = eventFixture({ kind: 'reminder' });
    event.endpoints[exit_endpoint] = { date: '2026-10-02', actual_price: null,
      status: 'pending', fetched_at: null, source: null };
    const prefs = preferences({ exit_endpoint, notifications: { reminder: true } });
    const time = Date.parse('2026-10-01T23:00:00Z');
    const reminder = notificationDecision(event, prefs, undefined, time);
    assert.equal(reminder.status, 'would_send');
    assert.equal(reminder.reason, 'confirmation_day_reminder');
    assert.equal(reminder.message, '今日は、設定した確定日です');
    const result = notificationDecision({ ...event, kind: 'result' }, prefs, undefined, time);
    assert.equal(result.status, 'suppressed');
    assert.equal(result.reason, 'result_notifications_removed');
    assert.notEqual(result.event_key, reminder.event_key);
  });
}

test('reminders are limited to the selected endpoint date and the 08 JST hour across a year boundary', () => {
  const event = eventFixture({ kind: 'reminder' });
  event.endpoints.d6_open.date = '2027-01-04';
  const prefs = preferences({ exit_endpoint: 'd6_open', notifications: { reminder: true } });
  for (const time of ['2027-01-03T22:59:59Z', '2027-01-04T00:00:00Z', '2027-01-02T23:00:00Z', '2026-12-31T23:00:00Z']) {
    assert.equal(notificationDecision(event, prefs, undefined, Date.parse(time)).reason, 'outside_reminder_window', time);
  }
  for (const time of ['2027-01-03T23:00:00Z', '2027-01-03T23:59:59Z']) {
    assert.equal(notificationDecision(event, prefs, undefined, Date.parse(time)).reason, 'confirmation_day_reminder', time);
  }
});

test('new-detection deduplication survives price-cap and D5/D6 preference changes', () => {
  const event = eventFixture({ kind: 'new_detection' });
  const first = notificationDecision(event, preferences({ notifications: { new_detection: true } }));
  const second = notificationDecision(event, preferences({ max_price: 5000, exit_endpoint: 'd6_open', notifications: { new_detection: true } }));
  assert.equal(first.status, 'would_send');
  assert.equal(second.status, 'would_send');
  assert.equal(first.event_key, second.event_key);
});

test('reminders distinguish D5 and D6 while keeping the same key after a cap change', () => {
  const first = notificationDecision(eventFixture({ kind: 'reminder' }));
  const capChanged = notificationDecision(eventFixture({ kind: 'reminder' }), preferences({ max_price: 5000, notifications: { new_detection: true } }));
  const endpointChanged = notificationDecision(eventFixture({ kind: 'reminder' }), preferences({ exit_endpoint: 'd6_open', notifications: { new_detection: true } }));
  assert.equal(first.event_key, capChanged.event_key);
  assert.notEqual(first.event_key, endpointChanged.event_key);
});

test('notification authorization rejects a stale, future, or missing membership check', () => {
  for (const checked_at of ['2026-10-02T06:59:29.999Z', '2026-10-02T07:00:00.001Z', '', null]) {
    const decision = notificationDecision(undefined, undefined, { ...membershipDecision(), checked_at });
    assert.equal(decision.status, 'held', String(checked_at));
    assert.equal(decision.reason, 'membership_check_stale');
  }
});

test('missing or malformed monetary values cannot silently become a paid total or zero refund', () => {
  for (const invalid of [true, false, null, '', '  ', [], {}]) {
    const total = memberFixture(); total.payment.total.amount = invalid;
    assert.notEqual(membershipDecision(total).status, 'paid', `total: ${JSON.stringify(invalid)}`);
    const refunded = memberFixture(); refunded.payment.refunded_amount.amount = invalid;
    assert.notEqual(membershipDecision(refunded).status, 'paid', `refund: ${JSON.stringify(invalid)}`);
  }
});

// The in-memory D1 double implements only statements used by the real API.
// Unique delivery keys are enforced at INSERT, including concurrent calls.
function fakeDatabase() {
  const state = { links: new Map(), preferences: new Map(), events: [], deliveries: new Map(),
    scanProgress: new Map(), scans: [], subscriptions: [], writes: [], failWrites: false, failProgressWrites: false };
  function prepare(sql) {
    const normalized = sql.replace(/\s+/g, ' ').trim();
    return {
      bind(...args) {
        return {
          async first() {
            if (normalized.includes('FROM cloud_member_links')) {
              const link = state.links.get(args[0]);
              return link?.discord_user_id === args[1] ? structuredClone(link) : null;
            }
            if (normalized.includes('FROM cloud_member_preferences')) {
              return state.preferences.has(args[0]) ? { preferences_json: state.preferences.get(args[0]) } : null;
            }
            if (normalized.includes('FROM cloud_notification_scan_progress')) {
              const progress = state.scanProgress.get(args[0]);
              return progress ? structuredClone(progress) : null;
            }
            if (normalized.includes('FROM cloud_notification_deliveries')) return state.deliveries.get(`${args[0]}|${args[1]}`) || null;
            throw new Error(`Unexpected first query: ${normalized}`);
          },
          async all() {
            assert.match(normalized, /FROM cloud_notification_events/);
            state.scans.push({ sql: normalized, args: plain(args) });
            if (normalized.includes('LIMIT 21')) {
              assert.match(normalized, /ORDER BY available_at ASC,\s*source_event_key ASC/);
              assert.match(normalized, /\(available_at,\s*source_event_key\) > \(\?,\s*\?\)/);
              assert.equal(args.length, 3);
              return { success: true, results: state.events
                .filter(row => row.available_at <= args[0] && (row.available_at > args[1] ||
                  (row.available_at === args[1] && row.source_event_key > args[2])))
                .sort((a, b) => a.available_at.localeCompare(b.available_at) || a.source_event_key.localeCompare(b.source_event_key))
                .slice(0, 21).map(row => structuredClone(row)) };
            }
            return { success: true, results: state.events.filter(row => row.available_at <= args[0])
              .sort((a, b) => b.available_at.localeCompare(a.available_at)).slice(0, 100)
              .map(row => ({ event_json: row.event_json, source_ledger_revision: row.source_ledger_revision })) };
          },
          async run() {
            state.writes.push({ sql: normalized, args: plain(args) });
            if (state.failWrites) return { success: false, error: 'synthetic write failure', meta: { changes: 0 } };
            if (normalized.startsWith('INSERT OR IGNORE INTO cloud_notification_scan_progress')) {
              if (state.scanProgress.has(args[0])) return { success: true, meta: { changes: 0 } };
              state.scanProgress.set(args[0], { after_available_at: '', after_source_event_key: '',
                cycle_cutoff_at: '', version: 0, updated_at: args[1] });
              return { success: true, meta: { changes: 1 } };
            }
            if (normalized.startsWith('UPDATE cloud_notification_scan_progress')) {
              if (state.failProgressWrites) return { success: false, error: 'synthetic cursor failure', meta: { changes: 0 } };
              const progress = state.scanProgress.get(args[4]);
              if (!progress || progress.version !== args[5]) return { success: true, meta: { changes: 0 } };
              state.scanProgress.set(args[4], { after_available_at: args[0], after_source_event_key: args[1],
                cycle_cutoff_at: args[2], version: progress.version + 1, updated_at: args[3] });
              return { success: true, meta: { changes: 1 } };
            }
            if (normalized.startsWith('INSERT INTO cloud_member_preferences')) {
              state.preferences.set(args[0], args[1]);
              return { success: true, meta: { changes: 1 } };
            }
            if (normalized.startsWith('UPDATE cloud_push_subscriptions')) {
              let changes = 0;
              for (const subscription of state.subscriptions) {
                if (subscription.member_id === args[1] && !subscription.revoked_at) {
                  subscription.revoked_at = args[0]; changes += 1;
                }
              }
              return { success: true, meta: { changes } };
            }
            if (normalized.startsWith('INSERT INTO cloud_notification_deliveries')) {
              const key = `${args[0]}|${args[1]}`;
              const existing = state.deliveries.get(key);
              if (['sent', 'dry_run_eligible'].includes(existing?.status)) return { success: true, meta: { changes: 0 } };
              state.deliveries.set(key, { member_id: args[0], event_key: args[1], status: args[2], reason: args[3],
                checked_at: args[4], membership_checked_at: args[5], attempts: (existing?.attempts || 0) + 1 });
              return { success: true, meta: { changes: 1 } };
            }
            throw new Error(`Unexpected run query: ${normalized}`);
          },
        };
      },
    };
  }
  return { state, prepare, batch: async (statements) => Promise.all(statements.map(statement => statement.run())) };
}

const SYNTHETIC_OWNER = '111111111111111111';
function syntheticResearchSnapshot() {
  const common = { detectionDate:'2026-01-05', triggerDate:'2026-01-06', simulatedEntryDate:'2026-01-07',
    entryBasis:'NEXT_SESSION_OPEN_AFTER_TRIGGER', entryPrice:123, pricePublicationStatus:'OWNER_ONLY_NOT_FOR_REDISTRIBUTION' };
  return { period:{first:'2026-01-05',last:'2026-11-12',sessions:209}, conditions:{costs:0},
    account:{portfolioReturn:0.001}, snapshot:{namespace:'research-a',accessScope:'SYNTHETIC_OWNER_ONLY',source:'SYNTHETIC_TEST_ONLY',marketPriceRedistributionApproved:false},
    closed:[{...common,rowId:'synthetic-closed',securityCode:'TEST-A',securityName:'SYNTHETIC-NEW-A-ONLY',state:'SIMULATED_CLOSED',simulatedExitDate:'2026-02-04',exitBasis:'CLOSE_ON_20TH_HOLDING_SESSION',exitPrice:124.5,holdingSessions:20,simulatedProfitJPY:150,simulatedReturn:0.01}],
    openAtEnd:[{...common,rowId:'synthetic-open',securityCode:'TEST-B',securityName:'SYNTHETIC-OPEN-A-ONLY',state:'SIMULATED_OPEN_AT_END',simulatedExitDate:null,exitBasis:null,exitPrice:null,valuationDate:'2026-11-12',observedHoldingSessions:2,simulatedUnrealizedProfitJPY:20,simulatedUnrealizedReturn:0.002}] };
}
async function assertNoLegacyData(response) {
  assert.doesNotMatch(await response.text(), /SECRET-UNRELEASED-TICKER|RELEASED-PUBLIC-ONLY|SYNTHETIC-(?:NEW|OPEN)-A|securityCode|entryPrice|must-never-leak|synthetic-(?:discord|whop)-(?:access|refresh|secret|read-key)/);
}
async function apiHarness({ fixture = memberFixture(), roles = ['paid-discord-role'], configured = true,
  providerStatus = 200, dbFailure = false, ownerOnly = false } = {}) {
  if (ownerOnly) fixture = {...fixture,link:{...fixture.link,discord_user_id:SYNTHETIC_OWNER}};
  const clock = { now: NOW };
  const calls = [];
  const assets = [];
  const provider = { status: providerStatus, fixture, discordRoles: roles, discordStatus:200, discordCalls:0 };
  const newA = { reads:0, unavailable:false };
  const modules = createModules({ clock, researchSnapshotReader:ownerOnly?async()=>{newA.reads++;if(newA.unavailable)throw new Error('SYNTHETIC-NEW-A-READ-FAILED');return syntheticResearchSnapshot();}:undefined, fetchMock: async (input, init = {}) => {
    const url = new URL(String(input));
    if(url.origin==='https://discord.com'){provider.discordCalls+=1;return Response.json({roles:provider.discordRoles},{status:provider.discordStatus});}
    assert.equal(url.origin, 'https://api.whop.com');
    assert.equal(init.method || 'GET', 'GET', 'No network mutation or push delivery is allowed.');
    assert.equal(init.headers.authorization, 'Bearer synthetic-whop-read-key');
    assert.equal(init.headers['Api-Version-Date'], rules.WHOP_API_VERSION);
    assert.equal(init.redirect, 'error');
    assert.equal(init.cache, 'no-store');
    calls.push({ path: url.pathname, query: Object.fromEntries(url.searchParams) });
    if (provider.status !== 200) return Response.json({ secret_provider_error: 'must-never-leak' }, { status: provider.status });
    if (url.pathname === '/api/v1/memberships/mem_1') return Response.json(provider.fixture.membership);
    if (url.pathname === '/api/v1/payments') return Response.json({ data: [provider.fixture.payment], pagination: { next_page: null } });
    if (url.pathname === `/api/v1/payments/${provider.fixture.payment.id}`) return Response.json(provider.fixture.payment);
    throw new Error(`Unexpected synthetic provider URL: ${url}`);
  } });
  const api = modules.load('./cloud-api');
  const worker = modules.load('./index').default;
  const gate = modules.load('./shared-report-gate');
  const db = fakeDatabase();
  const memberId = await api.cloudMemberId(fixture.link.discord_user_id);
  db.state.links.set(memberId, { ...fixture.link, member_id: memberId });
  const env = {
    DISCORD_CLIENT_ID: 'synthetic-discord-client', DISCORD_CLIENT_SECRET: 'synthetic-discord-secret',
    DISCORD_GUILD_ID: 'synthetic-guild', DISCORD_ALLOWED_ROLE_IDS: 'paid-discord-role',
    SESSION_SECRET: 'synthetic-session-encryption-key',
    ...(ownerOnly ? { CLOUD_OWNER_ONLY_ENABLED:'true', CLOUD_OWNER_DISCORD_ID:SYNTHETIC_OWNER } : {}),
    REPORT_ASSET_PATH: '/weak_early_beta_latest.html',
    CLOUD_DB: db,
    ...(configured ? { WHOP_API_KEY: 'synthetic-whop-read-key', WHOP_ACCOUNT_ID: 'biz_1',
      WHOP_PRODUCT_IDS: 'prod_1', WHOP_PAID_PLAN_IDS: 'plan_1' } : {}),
    ASSETS: { fetch: async input => {
      const pathname = new URL(String(input)).pathname;
      assets.push(pathname);
      return new Response(`<html><body>${pathname.endsWith('_free.html') ? 'RELEASED-PUBLIC-ONLY' : 'SECRET-UNRELEASED-TICKER'}</body></html>`);
    } },
  };
  env.CLOUD_ROLE_AUTHORITY = require('./helpers/cloud-role-authority.cjs').namespace(modules.load('./cloud-role-authority').CloudRoleAuthority,env);
  if (dbFailure) env.CLOUD_DB = { prepare() { throw new Error('synthetic db outage'); } };
  async function request(pathname = '/api/cloud/preferences', { method = 'GET', body, origin = 'https://gate.invalid', authenticated = true, subject } = {}) {
    const headers = new Headers();
    if (origin !== null) headers.set('origin', origin);
    if (authenticated) {
      const now = Math.floor(clock.now / 1000);
      const session = await gate.__test.createSession({ sub: subject || fixture.link.discord_user_id,
        accessToken: 'synthetic-discord-access', refreshToken: 'synthetic-discord-refresh', exp: now + 86400,
        tokenExp: now + 3600, roleCheckedAt: now, roles }, env.SESSION_SECRET);
      headers.set('cookie', `__Host-report_gate_session=${encodeURIComponent(session)}`);
    }
    if (body !== undefined) headers.set('content-type', 'application/json');
    return new Request(`https://gate.invalid${pathname}`, { method, headers, ...(body === undefined ? {} : { body: JSON.stringify(body) }) });
  }
  const fetchApi = async (pathname, options) => api.cloudApi(await request(pathname, options), env);
  return { api, worker, env, db, memberId, request, fetchApi, calls, assets, provider, clock, newA, subject:fixture.link.discord_user_id };
}

const bundlePath = (audience) => `/weak_early_beta_data_${audience}_analytics_${'a'.repeat(16)}_0000.json`;
for (const scenario of ['paid', 'free', 'expired', 'test', 'unlinked', 'provider-error', 'unconfigured']) {
  test(`new A preserves owner role contract and retires both legacy bundles for ${scenario}`, async () => {
    const fixture = memberFixture();
    if (scenario === 'expired') fixture.membership.current_period_end = '2026-10-01T00:00:00Z';
    if (scenario === 'test') fixture.link.environment = 'test';
    const h = await apiHarness({ fixture, ownerOnly:true, roles: scenario === 'free' ? [] : ['paid-discord-role'], configured: scenario !== 'unconfigured', providerStatus: scenario === 'provider-error' ? 503 : 200 });
    if (scenario === 'unlinked') h.db.state.links.clear();
    const details = await h.worker.fetch(await h.request('/api/research-a/details'), h.env);
    assert.equal(details.status, scenario === 'free' ? 403 : 200);
    assert.match(details.headers.get('cache-control'), /private.*no-store/);
    assert.equal(details.headers.get('vary'), 'Cookie');
    assert.equal(details.headers.get('cross-origin-resource-policy'), 'same-origin');
    assert.equal(details.headers.get('access-control-allow-origin'), null);
    if (scenario === 'free') { await assertNoLegacyData(details); assert.equal(h.newA.reads,0); }
    else { const data=await details.json();assert.equal(data.rows.length,2);assert(data.rows.every(r=>r.securityCode.startsWith('TEST-')));assert.equal(h.newA.reads,1); }
    for(const audience of ['full','free']){const retired=await h.worker.fetch(await h.request(bundlePath(audience)),h.env);assert.equal(retired.status,410);await assertNoLegacyData(retired);}
    assert.equal(h.assets.length,0);
    assert.equal(h.calls.length, 0, 'report access must not require another Whop login/check');
  });
}
test('new A rejects unauthenticated cross-origin malformed and mutating requests; legacy prefixes remain retired', async () => {
  const h = await apiHarness({ownerOnly:true});
  for (const [pathname, options, expected] of [
    ['/api/research-a/details', { authenticated: false }, 401],
    ['/api/research-a/details', { origin: 'https://elsewhere.invalid' }, 403],
    ['/api/research-a/details', { method: 'POST' }, 405],
    ['/api/research-a/details?q=x&q=y', {}, 400],
    ['/weak_early_beta_data_full_analytics_bad_0000.json', {}, 410],
  ]) {const before=h.newA.reads;const response=await h.worker.fetch(await h.request(pathname,options),h.env);assert.equal(response.status,expected);await assertNoLegacyData(response);if(expected!==400)assert.equal(h.newA.reads,before);}
  assert.equal(h.assets.length, 0);
});
test('new A follows the owner Discord role while delivery separately rechecks membership revocation', async () => {
  const h = await apiHarness({ownerOnly:true});
  assert.equal((await h.worker.fetch(await h.request('/api/research-a/details'), h.env)).status, 200);
  h.provider.fixture.membership.status = 'revoked';
  assert.equal((await h.worker.fetch(await h.request('/api/research-a/details'), h.env)).status, 200);
  assert.equal((await h.api.currentMembership(h.env, h.subject)).status, 'free');
  assert.equal(h.assets.length, 0);
  const head=await h.worker.fetch(await h.request('/api/research-a/details',{method:'HEAD'}),h.env);assert.equal(head.status,200);assert.equal(await head.text(),'');
  assert.equal((await h.worker.fetch(await h.request(bundlePath('free'), { method: 'HEAD' }), h.env)).status, 410);
});

test('API stores settings under the server session identity and returns private uncached JSON', async () => {
  const h = await apiHarness();
  const initial = await h.fetchApi();
  assert.equal(initial.status, 200);
  assert.equal(initial.headers.get('cache-control'), 'private, no-store');
  assert.equal(initial.headers.get('vary'), 'Cookie');
  assert.equal((await initial.json()).membership.status, 'paid');
  const selected = preferences({ max_price: 3000, exit_endpoint: 'd6_open', notifications: { new_detection: true } });
  const saved = await h.fetchApi(undefined, { method: 'PUT', body: selected });
  assert.equal(saved.status, 200);
  assert.deepEqual(JSON.parse(h.db.state.preferences.get(h.memberId)), selected);
  const retrieved = await h.fetchApi();
  assert.deepEqual((await retrieved.json()).preferences, selected);
  const otherUser = await h.fetchApi(undefined, { subject: 'other-discord-user' });
  const otherBody = await otherUser.json();
  assert.deepEqual(otherBody.preferences, plain(rules.DEFAULT_PREFERENCES));
  assert.equal(otherBody.membership.status, 'unverified');
  assert.doesNotMatch(JSON.stringify(otherBody), /other-discord-user|synthetic-.*(?:key|secret|access|refresh)/);
});

for (const [label, options] of [
  ['no session', { authenticated: false }],
  ['foreign origin', { origin: 'https://attacker.invalid' }],
  ['missing origin', { origin: null }],
]) {
  test(`API rejects a preference mutation with ${label}`, async () => {
    const h = await apiHarness();
    const response = await h.fetchApi(undefined, { method: 'PUT', body: preferences(), ...options });
    assert.ok([401, 403].includes(response.status));
    assert.equal(h.db.state.writes.length, 0);
  });
}

test('API rejects browser-supplied member IDs and email addresses', async () => {
  const h = await apiHarness();
  for (const extra of [{ member_id: 'someone-else' }, { email: 'unused@example.invalid' }]) {
    const response = await h.fetchApi(undefined, { method: 'PUT', body: { ...preferences(), ...extra } });
    assert.equal(response.status, 400);
  }
  assert.equal(h.db.state.writes.length, 0);
});

for (const [label, configure] of [
  ['expired membership', f => { f.membership.status = 'expired'; }],
  ['free grant', f => { f.payment.total.amount = '0'; }],
  ['test membership', f => { f.link.environment = 'test'; }],
]) {
  test(`API prevents opt-in for ${label} while allowing opt-out`, async () => {
    const fixture = memberFixture(); configure(fixture);
    const h = await apiHarness({ fixture });
    const enable = await h.fetchApi(undefined, { method: 'PUT', body: preferences({ notifications: { new_detection: true } }) });
    assert.equal(enable.status, 403);
    assert.equal(h.db.state.writes.length, 0);
    const disable = await h.fetchApi(undefined, { method: 'PUT', body: preferences() });
    assert.equal(disable.status, 200);
  });
}

test('a valid Whop member without the required Discord role cannot opt in or receive the full report', async () => {
  const h = await apiHarness({ roles: ['unrelated-role'] });
  const enable = await h.fetchApi(undefined, { method: 'PUT', body: preferences({ notifications: { new_detection: true } }) });
  assert.equal(enable.status, 403);
  const report = await h.worker.fetch(await h.request('/weak_early_beta_analytics.html'), h.env);
  assert.doesNotMatch(await report.text(), /SECRET-UNRELEASED-TICKER/);
  assert.equal(h.calls.length, 0);
});

test('legacy all-device unsubscribe is rejected without changing notifications or any device', async () => {
  const h = await apiHarness({ providerStatus: 503 });
  h.db.state.preferences.set(h.memberId, JSON.stringify(preferences({ notifications: { new_detection: true, reminder: true, result: true } })));
  h.db.state.subscriptions.push({ member_id: h.memberId, revoked_at: null }, { member_id: 'other-member', revoked_at: null });
  const response = await h.fetchApi('/api/cloud/push-subscriptions', { method: 'DELETE' });
  assert.equal(response.status, 405);
  assert.equal((await response.json()).ok, false);
  assert.equal(JSON.parse(h.db.state.preferences.get(h.memberId)).notifications.reminder,true);
  assert.equal(h.db.state.subscriptions[0].revoked_at,null);
  assert.equal(h.db.state.subscriptions[1].revoked_at, null);
});

test('notification OFF saves pause settings while preserving all existing device registrations',async()=>{
 const h=await apiHarness({providerStatus:503});
 h.db.state.subscriptions.push({member_id:h.memberId,revoked_at:null},{member_id:h.memberId,revoked_at:null},{member_id:'other-member',revoked_at:null});
 const response=await h.fetchApi('/api/cloud/preferences',{method:'PUT',body:preferences()});
 assert.equal(response.status,200);assert.deepEqual(JSON.parse(h.db.state.preferences.get(h.memberId)).notifications,preferences().notifications);
 assert.equal(h.db.state.subscriptions.every(row=>row.revoked_at===null),true);
});

test('each membership check re-reads Whop and a later 429 cannot reuse the earlier paid result', async () => {
  const h = await apiHarness();
  assert.equal((await h.api.currentMembership(h.env, 'discord-user-1')).status, 'paid');
  const firstReadCount = h.calls.length;
  assert.ok(firstReadCount >= 2);
  h.provider.status = 429;
  const denied = await h.api.currentMembership(h.env, 'discord-user-1');
  assert.equal(denied.status, 'unavailable');
  assert.ok(h.calls.length > firstReadCount);
  assert.doesNotMatch(JSON.stringify(denied), /must-never-leak|synthetic-whop-read-key/);
});

test('a renewed subscription uses its current paid receipt instead of the identity link initial payment', async () => {
  const fixture = memberFixture();
  fixture.payment.id = 'pay_renewal2';
  const h = await apiHarness({ fixture });
  const decision = await h.api.currentMembership(h.env, 'discord-user-1');
  assert.equal(decision.status, 'paid');
  const paymentList = h.calls.find(call => call.path === '/api/v1/payments');
  assert.ok(paymentList, 'Renewal verification must discover current payment receipts.');
  assert.equal(paymentList.query.account_id, 'biz_1');
  assert.equal(paymentList.query.membership_id, 'mem_1');
  assert.equal(paymentList.query.user_id, 'user_1');
  assert.equal(paymentList.query.status, 'paid');
  assert.ok(h.calls.some(call => call.path === '/api/v1/payments/pay_renewal2'));
  assert.equal(h.db.state.links.get(h.memberId).payment_id, 'pay_1', 'Provider verification does not rewrite identity evidence.');
});

test('unconfigured membership, a missing identity link, and a database outage fail closed', async () => {
  const h = await apiHarness({ configured: false });
  assert.equal((await h.api.currentMembership(h.env, 'discord-user-1')).status, 'unavailable');
  assert.equal(h.calls.length, 0);
  const missing = await apiHarness();
  missing.db.state.links.clear();
  assert.equal((await missing.api.currentMembership(missing.env, 'discord-user-1')).status, 'unverified');
  assert.equal(missing.calls.length, 0);
  const outage = await apiHarness({ dbFailure: true });
  assert.equal((await outage.fetchApi()).status, 503);
});

function addNotification(h, event = eventFixture()) {
  h.db.state.events.push({ source_event_key: `${event.signal_id}:${event.kind}`, available_at: '2026-10-02T07:00:00.000Z',
    event_json: JSON.stringify(event), source_ledger_revision: event.source_ledger_revision });
  h.db.state.preferences.set(h.memberId, JSON.stringify(preferences({ notifications: { new_detection: true } })));
}

function addBacklog(h, count, { prefix = 'private-backlog', sameTime = false } = {}) {
  const start = h.db.state.events.length;
  for (let index = 0; index < count; index += 1) {
    addNotification(h, eventFixture({ signal_id: `${prefix}-${String(index).padStart(3, '0')}` }));
    h.db.state.events[start + index].available_at = new Date(NOW - (sameTime ? 0 : index * 1000)).toISOString();
  }
}

async function dryRunPage(h, { subject } = {}) {
  const response = await h.fetchApi('/api/cloud/notifications/dry-run', { method: 'POST', body: {}, subject });
  assert.equal(response.status, 200);
  const body = await response.json();
  assert.equal(body.sent, 0);
  assert.equal(body.delivery_mode, 'dry_run');
  assert.doesNotMatch(JSON.stringify(body), /private-backlog|private-held|private-ties|private-concurrent|signal_id|event_key|actual_price|source_ledger_revision|after_available_at|cycle_cutoff_at/);
  assert.equal(body.scan.page_limit, 20);
  assert.equal(body.scan.processed, body.results.length);
  assert.ok(body.scan.processed <= 20);
  assert.equal(body.scan.cycle_complete, !body.scan.has_more);
  return body;
}

test('dry-run uses server events, never sends, and returns no private event identifiers', async () => {
  const h = await apiHarness(); addNotification(h);
  const response = await h.fetchApi('/api/cloud/notifications/dry-run', { method: 'POST', body: {} });
  assert.equal(response.status, 200);
  const body = await response.json();
  assert.equal(body.delivery_mode, 'dry_run');
  assert.equal(body.sent, 0);
  assert.deepEqual(body.results, [{ status: 'would_send', reason: 'new_detection' }]);
  assert.doesNotMatch(JSON.stringify(body), /signal-private-1|SECRET-UNRELEASED-TICKER|actual_price|event_key|message/);
  assert.equal([...h.db.state.deliveries.values()][0].status, 'dry_run_eligible');
  assert.equal([...h.db.state.deliveries.values()][0].attempts, 1);
  assert.ok(h.calls.every(call => call.path.startsWith('/api/v1/memberships') || call.path.startsWith('/api/v1/payments')));
});

test('default notification OFF also suppresses server-side dry-run candidates', async () => {
  const h = await apiHarness(); addNotification(h);
  h.db.state.preferences.clear();
  const response = await h.fetchApi('/api/cloud/notifications/dry-run', { method: 'POST', body: {} });
  const body = await response.json();
  assert.deepEqual(body.results, [{ status: 'suppressed', reason: 'notification_off' }]);
  assert.equal(body.sent, 0);
  assert.equal([...h.db.state.deliveries.values()][0].status, 'suppressed');
});

test('future notification candidates remain unavailable to a dry-run', async () => {
  const h = await apiHarness(); addNotification(h);
  h.db.state.events[0].available_at = '2026-10-03T07:00:00.000Z';
  const response = await h.fetchApi('/api/cloud/notifications/dry-run', { method: 'POST', body: {} });
  const body = await response.json();
  assert.deepEqual(body.results, []);
  assert.equal(body.sent, 0);
  assert.equal(h.db.state.deliveries.size, 0);
});

test('D1 write failures cannot be reported as saved settings, completed unsubscribe, or eligible receipts', async () => {
  const h = await apiHarness(); addNotification(h);
  h.db.state.failWrites = true;
  for (const [pathname, options] of [
    ['/api/cloud/preferences', { method: 'PUT', body: preferences({ max_price: 3000 }) }],
    ['/api/cloud/notifications/dry-run', { method: 'POST', body: {} }],
  ]) {
    const response = await h.fetchApi(pathname, options);
    assert.equal(response.status, 503, pathname);
    const body = await response.json();
    assert.equal(body.ok, false);
    assert.notEqual(body.unsubscribed, true);
    assert.doesNotMatch(JSON.stringify(body), /synthetic write failure/);
  }
  assert.equal(JSON.parse(h.db.state.preferences.get(h.memberId)).max_price, 1000);
  assert.equal(h.db.state.deliveries.size, 0);
});

test('dry-run refuses all browser-supplied event or recipient data', async () => {
  const h = await apiHarness(); addNotification(h);
  for (const body of [eventFixture(), { signal_id: 'attacker-signal' }, { member_id: 'other-member' }, { price: 1 }]) {
    const response = await h.fetchApi('/api/cloud/notifications/dry-run', { method: 'POST', body });
    assert.equal(response.status, 400);
  }
  assert.equal(h.db.state.deliveries.size, 0);
});

test('dry-run holds candidates lacking the canonical adapter version or matching ledger revision', async () => {
  for (const change of [
    (row, event) => { delete event.adapter_version; },
    (row, event) => { event.adapter_version = 'untrusted-adapter'; },
    (row, event) => { event.source_ledger_revision = 'd'.repeat(64); },
    (row) => { row.source_ledger_revision = 'not-a-sha'; },
  ]) {
    const h = await apiHarness(); addNotification(h);
    const row = h.db.state.events[0];
    const event = JSON.parse(row.event_json);
    change(row, event); row.event_json = JSON.stringify(event);
    const response = await h.fetchApi('/api/cloud/notifications/dry-run', { method: 'POST', body: {} });
    assert.equal(response.status, 200);
    const body = await response.json();
    assert.deepEqual(body.results, [{ status: 'held', reason: 'canonical_event_evidence_required' }]);
    assert.equal(body.sent, 0);
    assert.equal(h.db.state.deliveries.size, 0);
  }
});

test('dry-run deduplicates concurrent requests and subsequent retries atomically', async () => {
  const h = await apiHarness(); addNotification(h);
  const call = () => h.fetchApi('/api/cloud/notifications/dry-run', { method: 'POST', body: {} });
  const responses = await Promise.all([call(), call()]);
  const results = (await Promise.all(responses.map(response => response.json()))).flatMap(body => body.results);
  assert.equal(results.filter(result => result.status === 'would_send').length, 1);
  assert.equal(results.filter(result => result.reason === 'duplicate_event').length, 1);
  const retry = await (await call()).json();
  assert.deepEqual(retry.results, [{ status: 'suppressed', reason: 'duplicate_event' }]);
  assert.equal(h.db.state.deliveries.size, 1);
  assert.equal([...h.db.state.deliveries.values()][0].attempts, 1);
});

test('repeated dry-runs eventually evaluate all 205 available candidates with bounded pages', async () => {
  const h = await apiHarness();
  addBacklog(h, 205);
  const eligiblePerRun = [];
  for (let run = 0; run < 12; run += 1) {
    const body = await dryRunPage(h);
    eligiblePerRun.push(body.results.filter(result => result.status === 'would_send').length);
  }
  assert.equal(h.db.state.deliveries.size, 205,
    `All available candidates must be reachable; eligible counts by run: ${eligiblePerRun.join(', ')}`);
  assert.equal([...h.db.state.deliveries.values()].filter(row => row.status === 'dry_run_eligible').length, 205);
  assert.ok([...h.db.state.deliveries.values()].every(row => row.attempts === 1), 'Eligible candidates must not be duplicated on later runs.');
});

test('all 205 held candidates are reached and re-evaluated on the next scan after recovery', async () => {
  const h = await apiHarness({ providerStatus: 503 });
  addBacklog(h, 205, { prefix: 'private-held' });
  for (let page = 0; page < 11; page += 1) {
    const body = await dryRunPage(h);
    assert.ok(body.results.every(result => result.status === 'held'));
    assert.equal(body.scan.cycle_complete, page === 10);
  }
  assert.equal(h.db.state.deliveries.size, 205);
  assert.ok([...h.db.state.deliveries.values()].every(row => row.status === 'held' && row.attempts === 1));
  h.provider.status = 200;
  let eligible = 0;
  for (let page = 0; page < 11; page += 1) {
    const body = await dryRunPage(h);
    eligible += body.results.filter(result => result.status === 'would_send').length;
  }
  assert.equal(eligible, 205);
  assert.ok([...h.db.state.deliveries.values()].every(row => row.status === 'dry_run_eligible' && row.attempts === 2));
});

test('expired membership holds paginated candidates until a fresh API check confirms active status', async () => {
  const fixture = memberFixture(); fixture.membership.status = 'expired';
  const h = await apiHarness({ fixture }); addBacklog(h, 21);
  for (let page = 0; page < 2; page += 1) {
    const body = await dryRunPage(h);
    assert.ok(body.results.every(result => result.status === 'held' && result.reason === 'membership_not_paid_active'));
  }
  assert.equal(h.db.state.deliveries.size, 21);
  const priorProviderCalls = h.calls.length;
  h.provider.fixture.membership.status = 'active';
  let eligible = 0;
  for (let page = 0; page < 2; page += 1) {
    const body = await dryRunPage(h);
    eligible += body.results.filter(result => result.status === 'would_send').length;
  }
  assert.equal(eligible, 21);
  assert.ok(h.calls.length > priorProviderCalls, 'Restored membership must come from a fresh provider lookup.');
  assert.ok([...h.db.state.deliveries.values()].every(row => row.status === 'dry_run_eligible' && row.attempts === 2));
});

test('malformed private candidates are held without preventing the rest of a 205-row scan', async () => {
  const h = await apiHarness(); addBacklog(h, 205, { sameTime: true });
  h.db.state.events[0].event_json = 'malformed-json';
  h.db.state.events[1].event_json = 'null';
  const missingData = JSON.parse(h.db.state.events[2].event_json);
  delete missingData.endpoints;
  h.db.state.events[2].event_json = JSON.stringify(missingData);
  h.db.state.events[3].source_ledger_revision = 'mismatched-revision';
  let held = 0;
  let eligible = 0;
  for (let page = 0; page < 11; page += 1) {
    const body = await dryRunPage(h);
    held += body.results.filter(result => result.status === 'held').length;
    eligible += body.results.filter(result => result.status === 'would_send').length;
  }
  assert.equal(held, 4);
  assert.equal(eligible, 201);
  assert.equal(h.db.state.deliveries.size, 201);
  assert.equal(h.db.state.scanProgress.get(h.memberId).after_source_event_key, '');
});

test('the source-key tie-breaker reaches every one of 205 candidates with an identical timestamp', async () => {
  const h = await apiHarness();
  addBacklog(h, 205, { prefix: 'private-ties', sameTime: true });
  // Deliberately scramble insertion order so an implicit stable array order cannot pass.
  h.db.state.events.reverse();
  for (let page = 0; page < 11; page += 1) await dryRunPage(h);
  assert.equal(h.db.state.deliveries.size, 205);
  assert.ok([...h.db.state.deliveries.values()].every(row => row.attempts === 1));
  assert.equal(h.db.state.scanProgress.get(h.memberId).after_source_event_key, '');
  assert.equal(h.db.state.scanProgress.get(h.memberId).after_available_at, '');
});

test('overlapping paginated scans do not duplicate receipts or move the server cursor backwards', async () => {
  const h = await apiHarness();
  addBacklog(h, 205, { prefix: 'private-concurrent' });
  let eligible = 0;
  let lastVersion = 0;
  for (let round = 0; round < 12; round += 1) {
    const bodies = await Promise.all([dryRunPage(h), dryRunPage(h)]);
    eligible += bodies.flatMap(body => body.results).filter(result => result.status === 'would_send').length;
    const version = h.db.state.scanProgress.get(h.memberId).version;
    assert.ok(version > lastVersion);
    lastVersion = version;
  }
  assert.equal(eligible, 205);
  assert.equal(h.db.state.deliveries.size, 205);
  assert.ok([...h.db.state.deliveries.values()].every(row => row.status === 'dry_run_eligible' && row.attempts === 1));
  assert.ok(h.db.state.writes.filter(write => write.sql.startsWith('UPDATE cloud_notification_scan_progress'))
    .every(write => /WHERE member_id = \? AND version = \?/.test(write.sql)), 'Cursor updates must compare the original version.');
});

test('each authenticated member has an independent server-side scan position', async () => {
  const h = await apiHarness(); addBacklog(h, 45);
  await dryRunPage(h);
  const firstMemberPosition = structuredClone(h.db.state.scanProgress.get(h.memberId));
  const otherSubject = 'other-unlinked-discord-user';
  const otherMemberId = await h.api.cloudMemberId(otherSubject);
  h.db.state.preferences.set(otherMemberId, JSON.stringify(preferences({ notifications: { new_detection: true } })));
  const other = await dryRunPage(h, { subject: otherSubject });
  assert.equal(other.results.length, 20);
  assert.ok(other.results.every(result => result.status === 'held'));
  const otherPosition = structuredClone(h.db.state.scanProgress.get(otherMemberId));
  assert.equal(otherPosition.after_source_event_key, firstMemberPosition.after_source_event_key);
  await dryRunPage(h);
  assert.notEqual(h.db.state.scanProgress.get(h.memberId).after_source_event_key, firstMemberPosition.after_source_event_key);
  assert.deepEqual(h.db.state.scanProgress.get(otherMemberId), otherPosition);
  assert.equal([...h.db.state.deliveries.values()].filter(row => row.member_id === h.memberId).length, 40);
  assert.equal([...h.db.state.deliveries.values()].filter(row => row.member_id === otherMemberId).length, 20);
});

test('backdated and newly available candidates inserted mid-cycle are reached in the next bounded cycle', async () => {
  const h = await apiHarness(); addBacklog(h, 41);
  await dryRunPage(h);
  const cutoff = h.db.state.scanProgress.get(h.memberId).cycle_cutoff_at;
  addNotification(h, eventFixture({ signal_id: 'inserted-before-cursor' }));
  h.db.state.events.at(-1).available_at = new Date(NOW - 1000000).toISOString();
  addNotification(h, eventFixture({ signal_id: 'inserted-after-cycle-cutoff' }));
  h.db.state.events.at(-1).available_at = new Date(NOW + 1000).toISOString();
  h.clock.now = NOW + 2000;
  await dryRunPage(h);
  assert.equal(h.db.state.scanProgress.get(h.memberId).cycle_cutoff_at, cutoff);
  const last = await dryRunPage(h);
  assert.equal(last.scan.cycle_complete, true);
  assert.equal(h.db.state.deliveries.size, 41, 'Mid-cycle inserts must not make a supposedly bounded cycle unending.');
  for (let page = 0; page < 3; page += 1) await dryRunPage(h);
  assert.equal(h.db.state.deliveries.size, 43);
  assert.ok([...h.db.state.deliveries.values()].every(row => row.attempts === 1));
});

test('a failed cursor save can be retried without skipping a page or duplicating eligible receipts', async () => {
  const h = await apiHarness(); addBacklog(h, 21);
  h.db.state.failProgressWrites = true;
  const failed = await h.fetchApi('/api/cloud/notifications/dry-run', { method: 'POST', body: {} });
  assert.equal(failed.status, 503);
  assert.equal((await failed.json()).ok, false);
  assert.equal(h.db.state.deliveries.size, 20);
  assert.equal(h.db.state.scanProgress.get(h.memberId).version, 0);
  h.db.state.failProgressWrites = false;
  const retried = await dryRunPage(h);
  assert.ok(retried.results.every(result => result.reason === 'duplicate_event'));
  const finalPage = await dryRunPage(h);
  assert.equal(finalPage.results.length, 1);
  assert.equal(finalPage.results[0].status, 'would_send');
  assert.equal(h.db.state.deliveries.size, 21);
  assert.ok([...h.db.state.deliveries.values()].every(row => row.attempts === 1));
});

test('a held dry-run can be re-evaluated after provider recovery without claiming a send', async () => {
  const h = await apiHarness({ providerStatus: 503 }); addNotification(h);
  const call = () => h.fetchApi('/api/cloud/notifications/dry-run', { method: 'POST', body: {} });
  const held = await (await call()).json();
  assert.equal(held.results[0].status, 'held');
  h.provider.status = 200;
  const recovered = await (await call()).json();
  assert.equal(recovered.results[0].status, 'would_send');
  assert.equal(recovered.sent, 0);
  assert.equal([...h.db.state.deliveries.values()][0].attempts, 2);
  assert.equal([...h.db.state.deliveries.values()][0].status, 'dry_run_eligible');
});

for (const [label, setup] of [
  ['unconfigured provider', { configured: false }],
  ['provider unavailable', { providerStatus: 503 }],
  ['provider rate limited', { providerStatus: 429 }],
  ['expired membership', { fixture: (() => { const f = memberFixture(); f.membership.status = 'expired'; return f; })() }],
  ['test identity', { fixture: (() => { const f = memberFixture(); f.link.environment = 'test'; return f; })() }],
]) {
  test(`owner new A preserves Discord role access for ${label}, without another Whop login or legacy data`, async () => {
    const h = await apiHarness({...setup,ownerOnly:true});
    for (const pathname of ['/', '/report', '/research-a']) {
      const response = await h.worker.fetch(await h.request(pathname), h.env);
      assert.equal(response.status, 200);
      const html = await response.text();
      assert.match(html, /SYNTHETIC-NEW-A-ONLY/);
      assert.match(html,/天底極致 Cloud 2\.0/);assert.doesNotMatch(html,/SECRET-UNRELEASED-TICKER|RELEASED-PUBLIC-ONLY/);
      assert.match(response.headers.get('cache-control'), /private.*no-store/);
    }
    for(const pathname of ['/weak_early_beta_latest.html','/weak_early_beta_analytics.html','/weak_early_beta_fusion.html']){const retired=await h.worker.fetch(await h.request(pathname),h.env);assert.equal(retired.status,302);assert.equal(retired.headers.get('location'),'/research-a');await assertNoLegacyData(retired);}
    assert.equal(h.assets.length,0);
    assert.equal(h.calls.length, 0);
    const noRole = await apiHarness({ ...setup, ownerOnly:true, roles: [] });
    const denied = await noRole.worker.fetch(await noRole.request('/research-a'), noRole.env);
    assert.equal(denied.status,403);await assertNoLegacyData(denied);assert.equal(noRole.newA.reads,0);assert.equal(noRole.assets.length,0);
  });
}

test('valid owner Discord session and role retain new A and auth/check; legacy documents only redirect', async () => {
  const h = await apiHarness({ownerOnly:true});
  const retired=await h.worker.fetch(await h.request('/weak_early_beta_analytics.html'),h.env);assert.equal(retired.status,302);assert.equal(retired.headers.get('location'),'/research-a');await assertNoLegacyData(retired);
  const report = await h.worker.fetch(await h.request('/research-a'), h.env);
  assert.equal(report.status, 200);
  assert.match(await report.text(), /SYNTHETIC-NEW-A-ONLY/);
  const loggedOut = await h.worker.fetch(await h.request('/research-a', { authenticated: false }), h.env);
  assert.equal(loggedOut.status, 302);
  assert.match(loggedOut.headers.get('location'), /^\/auth\/login/);
  await assertNoLegacyData(loggedOut);
  const check = await h.worker.fetch(await h.request('/auth/check'), h.env);
  assert.equal(check.status, 200);
  h.provider.fixture.membership.status = 'expired';
  const sameRole = await h.worker.fetch(await h.request('/auth/check'), h.env);
  assert.equal(sameRole.status, 200);
  assert.equal((await h.api.currentMembership(h.env, h.subject)).status, 'free');assert.equal(h.assets.length,0);
});

for (const exit_endpoint of ['d5_close','d6_open']) test(`removed result ${exit_endpoint} is suppressed even for paid legacy opt-in`, () => {
 const legacy = preferences({ exit_endpoint, notifications: { result: true, new_detection: true, reminder: true } });
 for (const endpoints of [eventFixture().endpoints, { d5_close: { date: '2026-10-01' }, d6_open: { date: '2026-10-02' } }]) {
   const decision = notificationDecision(eventFixture({kind:'result',endpoints}),legacy);
   assert.equal(decision.status,'suppressed'); assert.equal(decision.reason,'result_notifications_removed'); assert.equal(decision.message,null);
 }
 assert.throws(() => rules.validatePreferences(legacy), /invalid_notifications/);
 const migrated = rules.validatePreferences(legacy,true);
 assert.equal('result' in migrated.notifications,false);
});
for (const base_shares of [0,1,99,101,150,1000001,NaN,Infinity,'100',true]) test(`invalid base shares ${base_shares} rejected`,()=>{
 assert.throws(()=>rules.validatePreferences(preferences({base_shares})),/invalid_base_shares/);
});
for (const cost_percent of [-1,10.01,0.001,NaN,Infinity,'0',true]) test(`invalid cost ${cost_percent} rejected`,()=>{
 assert.throws(()=>rules.validatePreferences(preferences({cost_percent})),/invalid_cost_percent/);
});
test('custom shares and fees survive server save and reload',async()=>{
 const h=await apiHarness(); const input=preferences({base_shares:300,cost_percent:0.25});
 const saved=await h.fetchApi('/api/cloud/preferences',{method:'PUT',body:input}); assert.equal(saved.status,200);
 const read=await h.fetchApi(); const body=await read.json(); assert.equal(body.preferences.base_shares,300);assert.equal(body.preferences.cost_percent,0.25);
});

test('hidden notification settings preserve authoritative opt-ins and other members without qualification lookup',async()=>{
 const h=await apiHarness({configured:false});
 const previous=preferences({notifications:{new_detection:true,reminder:true}});
 h.db.state.preferences.set(h.memberId,JSON.stringify(previous));
 const input=preferences({max_price:2000,base_shares:200});delete input.notifications;
 const other=await h.worker.fetch(await h.request('/api/cloud/preferences',{method:'PUT',body:input,subject:'other-discord-user'}),h.env);
 assert.equal(other.status,200);assert.deepEqual((await other.json()).preferences.notifications,{new_detection:false,reminder:false});
 const saved=await h.fetchApi('/api/cloud/preferences',{method:'PUT',body:input});
 assert.equal(saved.status,200);assert.deepEqual((await saved.json()).preferences.notifications,previous.notifications);
 assert.equal(JSON.parse(h.db.state.preferences.get(h.memberId)).max_price,2000);
 assert.equal(h.db.state.preferences.size,2);assert.equal(h.calls.length,0);
});

test('hidden notification preference read skips redundant roles without qualifying notifications or reports', async () => {
 const h=await apiHarness({ownerOnly:true}); h.env.CLOUD_PUSH_MEMBERSHIP_POLICY='whop_managed_discord_role'; h.provider.discordStatus=429;
 const saved=preferences({notifications:{new_detection:true,reminder:true}});h.db.state.preferences.set(h.memberId,JSON.stringify(saved));
 const response=await h.fetchApi('/api/cloud/preferences?notification_status=omit'); assert.equal(response.status,200);
 const body=await response.json();assert.deepEqual(body.preferences,saved);assert.equal(body.membership.status,'unavailable');assert.equal(body.membership.reason,'notification_status_not_requested');assert.equal(body.notification_eligible,false);assert.equal(h.provider.discordCalls,0);
 const anonymous=await h.fetchApi('/api/cloud/preferences?notification_status=omit',{authenticated:false});assert.equal(anonymous.status,401);
 const report=await h.worker.fetch(await h.request('/research-a?notification_status=omit'),h.env);
 assert.equal(report.status,503);await assertNoLegacyData(report);assert.equal(h.provider.discordCalls,1);assert.equal(h.newA.reads,0);assert.equal(h.assets.length,0);
});

test('notification-OFF settings save without Whop configuration and stay isolated across two Discord sessions', async () => {
  const h = await apiHarness({ configured: false });
  const users = [
    ['discord-user-1', preferences({ max_price: 2000, base_shares: 200 })],
    ['other-discord-user', preferences({ max_price: 5000, base_shares: 300, exit_endpoint: 'd6_open' })],
  ];
  for (const [subject, body] of users) {
    const saved = await h.worker.fetch(await h.request('/api/cloud/preferences', { method: 'PUT', body, subject }), h.env);
    assert.equal(saved.status, 200);
    assert.equal((await saved.json()).persistence, 'server');
  }
  for (const [subject, expected] of users) {
    const read = await h.worker.fetch(await h.request('/api/cloud/preferences?member_id=forged-target', { subject }), h.env);
    assert.equal(read.status, 200);
    assert.deepEqual((await read.json()).preferences, expected);
  }
  assert.equal(h.db.state.preferences.size, 2);
  assert.equal(h.calls.length, 0, 'Whop must not be contacted when absent');
  const enabled = await h.worker.fetch(await h.request('/api/cloud/preferences', {
    method: 'PUT', body: preferences({ notifications: { new_detection: true } }),
  }), h.env);
  assert.equal(enabled.status, 403);
});

for(const [label,options,expected] of [['anonymous',{authenticated:false},'login'],['free',{},'free'],['paid',{},'full']])test('owner Cloud new A initially authenticates without legacy free fallback: '+label,async()=>{
 const h=await apiHarness({ownerOnly:true,roles:label==='paid'?['paid-discord-role']:[]});
 for(const path of ['/','/report','/research-a']){
  const response=await h.worker.fetch(await h.request(path,options),h.env);
  if(expected==='login'){assert.equal(response.status,302);assert.match(response.headers.get('location'),/^\/auth\/login/);await assertNoLegacyData(response);continue;}
  assert.equal(response.status,expected==='free'?403:200);
  if(expected==='free')await assertNoLegacyData(response);else{const html=await response.text();assert.match(html,/SYNTHETIC-NEW-A-ONLY/);assert.doesNotMatch(html,/SECRET-UNRELEASED-TICKER|RELEASED-PUBLIC-ONLY/);}
 }
 const details=await h.worker.fetch(await h.request('/api/research-a/details',options),h.env);assert.equal(details.status,expected==='full'?200:label==='anonymous'?401:403);if(expected!=='full'){await assertNoLegacyData(details);assert.equal(h.newA.reads,0);}else assert.equal((await details.json()).rows.length,2);
 for(const audience of ['free','full']){const retired=await h.worker.fetch(await h.request(bundlePath(audience),options),h.env);assert.equal(retired.status,label==='anonymous'?401:410);await assertNoLegacyData(retired);}
 assert.equal(h.assets.length,0);assert.equal(h.calls.length,0);
});

for(const [label,status,roles] of [['revoked',200,[]],['429',429,['paid-discord-role']],['503',503,['paid-discord-role']],['401',401,['paid-discord-role']],['403',403,['paid-discord-role']]])test('cached owner session exposes neither new A nor legacy fallback after '+label,async()=>{
 const h=await apiHarness({ownerOnly:true});h.provider.discordRoles=roles;h.provider.discordStatus=status;
 const document=await h.worker.fetch(await h.request('/research-a'),h.env);
 assert.equal(document.status,label==='revoked'?403:503);await assertNoLegacyData(document);
 const details=await h.worker.fetch(await h.request('/api/research-a/details'),h.env);assert.equal(details.status,label==='revoked'?403:503);await assertNoLegacyData(details);
 for(const audience of ['full','free']){const retired=await h.worker.fetch(await h.request(bundlePath(audience)),h.env);assert.equal(retired.status,410);await assertNoLegacyData(retired);}
 const anonymous=await h.worker.fetch(await h.request(bundlePath('free'),{authenticated:false}),h.env);assert.equal(anonymous.status,401);await assertNoLegacyData(anonymous);
 assert.equal(h.assets.length,0);assert.equal(h.newA.reads,0);
});

test('approved authority shares 90 seconds across owner new A and auth/check then confirms revocation',async()=>{
 const h=await apiHarness({ownerOnly:true});
 for(const path of ['/research-a','/api/research-a/details','/research-a/details.json','/auth/check']) assert.equal((await h.worker.fetch(await h.request(path),h.env)).status,200);
 assert.equal(h.provider.discordCalls,1);
 h.provider.discordRoles=[];h.clock.now+=90000;
 const reads=h.newA.reads,doc=await h.worker.fetch(await h.request('/research-a'),h.env);assert.equal(doc.status,403);await assertNoLegacyData(doc);
 const details=await h.worker.fetch(await h.request('/api/research-a/details'),h.env);assert.equal(details.status,403);await assertNoLegacyData(details);assert.equal(h.provider.discordCalls,2);assert.equal(h.newA.reads,reads);assert.equal(h.assets.length,0);
});
test('expired authority failure closes owner new A without legacy fallback while settings remain writable',async()=>{
 const h=await apiHarness({ownerOnly:true});h.env.CLOUD_PUSH_MEMBERSHIP_POLICY='whop_managed_discord_role';
 await h.worker.fetch(await h.request('/research-a'),h.env);const reads=h.newA.reads;h.clock.now+=90000;h.provider.discordStatus=429;
 const doc=await h.worker.fetch(await h.request('/research-a'),h.env);assert.equal(doc.status,503);await assertNoLegacyData(doc);
 const check=await h.worker.fetch(await h.request('/auth/check'),h.env);assert.equal(check.status,503);assert.equal((await check.json()).reason,'discord_role_lookup_429');
 const details=await h.worker.fetch(await h.request('/api/research-a/details'),h.env);assert.equal(details.status,503);await assertNoLegacyData(details);assert.equal(h.newA.reads,reads);
 for(const audience of ['full','free']){const retired=await h.worker.fetch(await h.request(bundlePath(audience)),h.env);assert.equal(retired.status,410);await assertNoLegacyData(retired);}assert.equal(h.assets.length,0);
 const input=preferences();delete input.notifications;
 const save=await h.worker.fetch(await h.request('/api/cloud/preferences',{method:'PUT',body:input}),h.env);assert.equal(save.status,200);
 assert.equal(h.provider.discordCalls,2);
});
