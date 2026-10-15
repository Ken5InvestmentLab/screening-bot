import assert from 'node:assert/strict';
import test from 'node:test';
import { networkFailureDetail, parseDynamicPorts, summarizePortPressure, inspectWindowsNetwork,
  waitForNetworkCapacity } from './weak-early-beta-network-guard.mjs';

const ranges = { ipv4: { start: 49152, count: 16384 }, ipv6: { start: 49152, count: 16384 } };
const row = (port, remote = '1.2.3.4:443', owner = '123') => `  TCP  192.0.2.1:${port}  ${remote}  ESTABLISHED  ${owner}`;

test('network failure summaries keep actual category without copying log secrets', () => {
  assert.deepEqual(networkFailureDetail('[WinError 10048] request https://secret.example/token'), {
    failureType: 'windows_tcp_ports_exhausted', message: 'Windows TCP port resources exhausted (10048)',
  });
  assert.equal(networkFailureDetail('curl: (7) failed').failureType, 'network_connection_failed');
  assert.equal(networkFailureDetail('Yahoo did not return split actions'), null);
  assert.equal(networkFailureDetail('certificate verification failed'), null);
  assert.equal(networkFailureDetail('curl: (7) failed\nrequest recovered\nCorporateActionError: unexplained source revision'), null);
  assert.equal(networkFailureDetail('[WinError 10048] old failure\nValueError: schema is invalid\n'), null);
});

test('localized dynamic port ranges are validated without assuming English labels', () => {
  assert.deepEqual(parseDynamicPorts('プロトコル tcp\n開始ポート : 49152\nポート数 : 16384'), ranges.ipv4);
  for (const text of ['', 'Start : 49152', 'Start : 65535\nCount : 2', 'Start : 0\nCount : 100']) {
    assert.throws(() => parseDynamicPorts(text));
  }
});

test('orphan sockets count, duplicate endpoints do not inflate port pressure', () => {
  const lines = Array.from({ length: 15585 }, (_, i) => row(49152 + i, '1.2.3.4:443', '30120'));
  lines.push(row(49152, '5.6.7.8:443', '30120'));
  const result = summarizePortPressure(lines.join('\n'), ranges);
  assert.equal(result.blocked, true);
  assert.equal(result.groups[0].used, 15585);
  assert.equal(result.groups[0].remaining, 799);
});

test('IPv4 and IPv6 ranges and local addresses are accounted separately', () => {
  const result = summarizePortPressure([row(100), row(49152),
    ' TCP [::1]:49152 [::1]:443 TIME_WAIT 0', ' TCP 127.0.0.1:49152 127.0.0.1:80 CLOSE_WAIT 8'].join('\n'), ranges);
  assert.equal(result.blocked, false);
  assert.equal(result.groups.length, 3);
  assert.ok(result.groups.every(group => group.used === 1));
  assert.throws(() => summarizePortPressure('TCP malformed endpoint', ranges));
  assert.throws(() => summarizePortPressure('', ranges));
});

test('inspection is read-only and accepts a large connection table without a 1 MiB cap', async () => {
  const calls = [];
  const result = await inspectWindowsNetwork({ exec: async (exe, args, options) => {
    calls.push([exe, args]);
    assert.ok(options.maxBuffer > 1024 * 1024);
    assert.equal(options.windowsHide, true);
    return { stdout: exe === 'netsh.exe' ? 'Start : 49152\nCount : 16384' : row(49152) };
  } });
  assert.equal(result.blocked, false);
  assert.equal(calls.length, 3);
  assert.deepEqual(calls[2], ['netstat.exe', ['-ano']]);
  assert.ok(calls.every(([exe, args]) => exe === 'netstat.exe' || args.includes('show')));
});

function clockFixture() {
  let time = 0;
  return { now: () => time, sleep: async ms => { time += ms; } };
}

test('capacity recovery waits without invoking acquisition or any destructive action', async () => {
  const status = [];
  let inspections = 0;
  const result = await waitForNetworkCapacity({ platform: 'win32', ...clockFixture(), timeoutMs: 60,
    pollMs: 30, inspect: async () => ({ blocked: ++inspections < 3 }),
    onProgress: progress => status.push(progress.status),
  });
  assert.deepEqual(status, ['waiting', 'waiting', 'ready']);
  assert.equal(result.waitedMs, 60);
});

test('persistent exhaustion, failed inspection, and JST rollover stop before acquisition', async () => {
  await assert.rejects(waitForNetworkCapacity({ platform: 'win32', ...clockFixture(), timeoutMs: 60,
    pollMs: 30, inspect: async () => ({ blocked: true }),
  }), /ports remain exhausted/);
  await assert.rejects(waitForNetworkCapacity({ platform: 'win32', inspect: async () => { throw Error('denied'); } }), /denied/);
  let date = '2026-10-15';
  const clock = clockFixture();
  await assert.rejects(waitForNetworkCapacity({ platform: 'win32', now: clock.now,
    sleep: async ms => { await clock.sleep(ms); date = '2026-10-16'; }, pollMs: 1,
    expectedDate: '2026-10-15', currentDate: () => date,
    inspect: async () => ({ blocked: true }),
  }), /crossed its JST run date/);
});

test('non-Windows hosts never invoke Windows tools and wait settings are bounded', async () => {
  assert.deepEqual(await waitForNetworkCapacity({ platform: 'linux', inspect: async () => { throw Error('unexpected'); } }), { skipped: 'non_windows' });
  for (const value of [-1, 1_800_001, NaN]) {
    await assert.rejects(waitForNetworkCapacity({ timeoutMs: value }), /Invalid bounded/);
  }
});

test('a slow inspection cannot permit acquisition on the next JST date', async () => {
  let date = '2026-10-15';
  await assert.rejects(waitForNetworkCapacity({ platform: 'win32',
    expectedDate: date, currentDate: () => date,
    inspect: async () => { date = '2026-10-16'; return { blocked: false }; },
  }), /crossed its JST run date/);
});

test('a recovered inspection after the absolute deadline cannot begin acquisition', async () => {
  let time = 0;
  let inspections = 0;
  const budgets = [];
  await assert.rejects(waitForNetworkCapacity({ platform: 'win32', timeoutMs: 10, pollMs: 10,
    now: () => time, sleep: async ms => { time += ms; },
    inspect: async ({ timeoutMs }) => {
      budgets.push(timeoutMs); time += 6;
      return { blocked: ++inspections < 2 };
    },
  }), /exceeded its deadline/);
  assert.equal(inspections, 2);
  assert.deepEqual(budgets, [10, 1]);
});
