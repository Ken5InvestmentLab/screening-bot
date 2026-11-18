import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { networkFailureDetail, parseDynamicPorts, summarizePortPressure, inspectWindowsNetwork,
  waitForNetworkCapacity, withWindowsDetectionTrust } from './weak-early-beta-network-guard.mjs';

const ranges = { ipv4: { start: 49152, count: 16384 }, ipv6: { start: 49152, count: 16384 } };
const row = (port, remote = '1.2.3.4:443', owner = '123') => `  TCP  192.0.2.1:${port}  ${remote}  ESTABLISHED  ${owner}`;

test('network failure summaries keep actual category without copying log secrets', () => {
  assert.deepEqual(networkFailureDetail('[WinError 10048] request https://secret.example/token'), {
    failureType: 'windows_tcp_ports_exhausted', message: 'Windows TCP port resources exhausted (10048)',
  });
  assert.equal(networkFailureDetail('curl: (7) failed').failureType, 'network_connection_failed');
  assert.deepEqual(networkFailureDetail('progress\nCorporateActionError: curl: (77) error setting certificate file: private path'), {
    failureType: 'tls_ca_bundle_unavailable', message: 'Windows Yahoo TLS CA bundle could not be loaded',
  });
  assert.equal(networkFailureDetail('curl: (77) prior warning\nCorporateActionError: source quality failed'), null);
  assert.equal(networkFailureDetail('Yahoo did not return split actions'), null);
  assert.equal(networkFailureDetail('certificate verification failed'), null);
  assert.equal(networkFailureDetail('curl: (7) failed\nrequest recovered\nCorporateActionError: unexplained source revision'), null);
  assert.equal(networkFailureDetail('[WinError 10048] old failure\nValueError: schema is invalid\n'), null);
});

function trustFixture(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'cloud-ca-test-'));
  t.after(() => {
    for (const file of fs.readdirSync(root, { withFileTypes: true })) {
      const localPath = path.join(root, file.name);
      if (file.isDirectory()) fs.rmdirSync(localPath);
      else fs.unlinkSync(localPath);
    }
    fs.rmdirSync(root);
  });
  const temp = path.join(root, 'Temp');
  fs.mkdirSync(temp);
  const bundle = (name, bytes) => {
    const file = path.join(root, name);
    fs.writeFileSync(file, bytes);
    return file;
  };
  const defaultBundle = bundle('既定.pem', 'test default bytes\n');
  const env = { LOCALAPPDATA: root };
  const python = path.join(root, 'configured python.exe');
  const probe = (selected = defaultBundle) => async (executable, args, options) => {
    assert.equal(executable, python);
    assert.equal(args[0], '-B');
    assert.match(args[2], /curl_cffi\.curl import DEFAULT_CACERT/);
    assert.equal(options.cwd, root);
    assert.equal(options.env, env);
    assert.ok(options.timeout <= 20_000);
    return { stdout: JSON.stringify(selected) };
  };
  const options = { platform: 'win32', cwd: root, python, env };
  return { root, temp, defaultBundle, env, bundle, probe, options };
}

test('the configured interpreter default is copied exactly for the live child and removed after it exits', async t => {
  const f = trustFixture(t);
  const priorGlobal = process.env.SSL_CERT_FILE;
  let alias;
  const result = await withWindowsDetectionTrust({ ...f.options, exec: f.probe() }, env => {
    alias = env.SSL_CERT_FILE;
    assert.match(alias, /^[\x20-\x7e]+$/);
    assert.equal(path.dirname(path.dirname(alias)), fs.realpathSync.native(f.temp));
    assert.deepEqual(fs.readFileSync(alias), fs.readFileSync(f.defaultBundle));
    assert.equal(env.REQUESTS_CA_BUNDLE, undefined);
    assert.equal(env.CURL_CA_BUNDLE, undefined);
    assert.equal(f.env.SSL_CERT_FILE, undefined);
    return 'ran';
  });
  assert.equal(result, 'ran');
  assert.equal(fs.existsSync(alias), false);
  assert.deepEqual(fs.readdirSync(f.temp), []);
  assert.equal(process.env.SSL_CERT_FILE, priorGlobal);
});

test('explicit CA sources preserve differing precedence and bytes without replacing an ASCII override', async t => {
  const f = trustFixture(t);
  const curl = f.bundle('curl.pem', 'curl-specific bytes\r\n');
  const requests = f.bundle('要求用.pem', 'requests-specific bytes\n');
  Object.assign(f.env, { ssl_cert_file: f.defaultBundle, CURL_CA_BUNDLE: curl, REQUESTS_CA_BUNDLE: requests });
  const original = { ...f.env };
  await withWindowsDetectionTrust({ ...f.options, exec: f.probe() }, env => {
    assert.deepEqual(fs.readFileSync(env.ssl_cert_file), fs.readFileSync(f.defaultBundle));
    assert.deepEqual(fs.readFileSync(env.REQUESTS_CA_BUNDLE), fs.readFileSync(requests));
    assert.notEqual(env.ssl_cert_file, env.REQUESTS_CA_BUNDLE);
    assert.equal(env.CURL_CA_BUNDLE, curl);
    assert.equal(env.SSL_CERT_FILE, undefined);
  });
  assert.deepEqual(f.env, original);
  assert.deepEqual(fs.readdirSync(f.temp), []);
});

test('missing or conflicting explicit CA policies and an unusable alias root stop before the detection child', async t => {
  const f = trustFixture(t);
  const never = () => assert.fail('detection must not start');
  const fail = { failureType: 'tls_ca_bundle_unavailable' };
  f.env.SSL_CERT_FILE = path.join(f.root, 'missing.pem');
  await assert.rejects(withWindowsDetectionTrust({ ...f.options, exec: never }, never), fail);
  f.env.SSL_CERT_FILE = f.bundle('custom.pem', 'a different explicit CA');
  await assert.rejects(withWindowsDetectionTrust({ ...f.options, exec: f.probe() }, never), fail);
  delete f.env.SSL_CERT_FILE;
  f.env.LOCALAPPDATA = path.join(f.root, '非ASCII-temp');
  const nonAsciiTemp = path.join(f.env.LOCALAPPDATA, 'Temp');
  fs.mkdirSync(nonAsciiTemp, { recursive: true });
  try {
    await assert.rejects(withWindowsDetectionTrust({ ...f.options, exec: f.probe() }, never), fail);
    assert.deepEqual(fs.readdirSync(nonAsciiTemp), []);
  } finally {
    fs.rmdirSync(nonAsciiTemp);
    fs.rmdirSync(f.env.LOCALAPPDATA);
  }
  assert.deepEqual(fs.readdirSync(f.temp), []);
});

test('child failure is preserved and temporary CA material is cleaned without retrying', async t => {
  const f = trustFixture(t);
  const childError = new Error('terminal TLS failure');
  let calls = 0;
  await assert.rejects(withWindowsDetectionTrust({ ...f.options, exec: f.probe() }, env => {
    calls += 1;
    assert.equal(fs.existsSync(env.SSL_CERT_FILE), true);
    throw childError;
  }), childError);
  assert.equal(calls, 1);
  assert.deepEqual(fs.readdirSync(f.temp), []);
});

test('an ASCII default or a non-Windows process leaves CA variables alone', async t => {
  const f = trustFixture(t);
  const asciiBundle = f.bundle('ascii.pem', 'test default bytes\n');
  await withWindowsDetectionTrust({ ...f.options, exec: f.probe(asciiBundle) }, env => {
    assert.deepEqual(env, f.env);
  });
  await withWindowsDetectionTrust({ ...f.options, platform: 'linux', exec: () => assert.fail('no probe') }, env => {
    assert.equal(env, f.env);
  });
  assert.deepEqual(fs.readdirSync(f.temp), []);
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
