import { execFile } from 'node:child_process';
import { createHash } from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { promisify } from 'node:util';

const execute = promisify(execFile);
const caVariables = ['SSL_CERT_FILE', 'CURL_CA_BUNDLE', 'REQUESTS_CA_BUNDLE'];
const asciiPath = value => /^[\x20-\x7e]+$/.test(value);
const sha256 = bytes => createHash('sha256').update(bytes).digest('hex');
const caFailureType = 'tls_ca_bundle_unavailable';

export async function withWindowsDetectionTrust({
  python, cwd, env, platform = process.platform, exec = execute,
}, operation) {
  if (platform !== 'win32') return operation(env);
  let directory;
  const aliases = new Map();
  const childEnv = { ...env };
  try {
    try {
      const envKey = name => {
        const matches = Object.keys(env).filter(key => key.toUpperCase() === name);
        if (matches.length > 1) throw new Error('ambiguous case-insensitive CA configuration');
        return matches[0] ?? name;
      };
      const checkedFile = value => {
        const file = fs.realpathSync.native(path.resolve(cwd, value));
        if (!fs.statSync(file).isFile()) throw new Error('CA bundle is not a regular file');
        fs.closeSync(fs.openSync(file, 'r'));
        return file;
      };
      const explicit = caVariables.map(envKey).filter(key => env[key]).map(key => ({
        key, value: env[key], file: checkedFile(env[key]),
      }));
      // curl_cffi fixes its default when imported, including inside yfinance.
      // Use the configured interpreter to resolve it without making a request.
      const { stdout } = await exec(python, ['-B', '-c',
        'import json; from curl_cffi.curl import DEFAULT_CACERT; print(json.dumps(DEFAULT_CACERT))',
      ], { cwd, env, encoding: 'utf8', windowsHide: true, timeout: 20_000, maxBuffer: 16_384 });
      const selected = JSON.parse(stdout);
      if (typeof selected !== 'string' || !selected) throw new Error('invalid CA bundle probe');
      const defaultFile = checkedFile(selected);
      if (explicit.length && explicit[0].file !== defaultFile) throw new Error('CA configuration and interpreter disagree');

      const alias = file => {
        if (aliases.has(file)) return aliases.get(file);
        if (!directory) {
          const localAppData = env[envKey('LOCALAPPDATA')];
          if (!localAppData || !path.isAbsolute(localAppData)) throw new Error('missing local AppData');
          const appData = fs.realpathSync.native(localAppData);
          const temp = fs.realpathSync.native(path.join(appData, 'Temp'));
          if (path.dirname(temp) !== appData || !asciiPath(temp)) throw new Error('invalid local CA alias directory');
          directory = fs.mkdtempSync(path.join(temp, 'cloud-ca-'));
        }
        const target = path.join(directory, `ca-${aliases.size}.pem`);
        const bytes = fs.readFileSync(file);
        aliases.set(file, target);
        fs.writeFileSync(target, bytes, { flag: 'wx' });
        if (sha256(fs.readFileSync(target)) !== sha256(bytes)) throw new Error('CA alias differs from original');
        return target;
      };
      // Keep each variable's certificate policy. curl_cffi's default and
      // Requests-compatible sessions use different precedence orders.
      for (const { key, value, file } of explicit) {
        if (!asciiPath(value) || !asciiPath(file)) childEnv[key] = alias(file);
      }
      if (!explicit.length && (!asciiPath(selected) || !asciiPath(defaultFile))) {
        childEnv[envKey('SSL_CERT_FILE')] = alias(defaultFile);
      }
    } catch {
      throw Object.assign(new Error('Windows Yahoo TLS CA bundle unavailable; check the CA files and local temporary directory'),
        { failureType: caFailureType });
    }
    return await operation(childEnv);
  } finally {
    if (directory) {
      // Remove only the PEM files and fresh directory created by this call.
      try {
        for (const file of aliases.values()) fs.rmSync(file, { force: true });
        fs.rmdirSync(directory);
      } catch {
        console.error('Could not remove the temporary Cloud CA bundle');
      }
    }
  }
}

export function networkFailureDetail(stderr) {
  // Only fixed classifications leave bounded local logs. Never copy an error
  // line that could contain authentication values into receipts or Discord.
  // Earlier attempts may have recovered. Only the terminal diagnostic can
  // classify this failed command; historical log lines are not its cause.
  const terminal = String(stderr).trim().split(/\r?\n/).at(-1) || '';
  if (/curl:\s*\(77\)/i.test(terminal)) {
    return { failureType: caFailureType, message: 'Windows Yahoo TLS CA bundle could not be loaded' };
  }
  if (/(?:WinError|os error)\s*10048\b|WSAEADDRINUSE/.test(terminal)) {
    return { failureType: 'windows_tcp_ports_exhausted',
      message: 'Windows TCP port resources exhausted (10048)' };
  }
  if (/curl:\s*\(7\)|Failed to establish a new connection|ConnectionRefusedError/.test(terminal)) {
    return { failureType: 'network_connection_failed', message: 'Network connection failed during acquisition' };
  }
  return null;
}

export function parseDynamicPorts(output) {
  // netsh labels are localized; the two value lines end in ASCII integers.
  const values = output.split(/\r?\n/).map(line => line.match(/:\s*(\d+)\s*$/))
    .filter(Boolean).map(match => Number(match[1]));
  if (values.length !== 2 || values[0] < 1024 || values[1] < 1 || values[0] + values[1] > 65536) {
    throw new Error('Cannot verify Windows TCP dynamic port range');
  }
  return { start: values[0], count: values[1] };
}

export function summarizePortPressure(output, ranges) {
  const addresses = new Map();
  let rows = 0;
  for (const line of output.split(/\r?\n/)) {
    if (!/^\s*TCP\s/i.test(line)) continue;
    rows += 1;
    const fields = line.trim().split(/\s+/);
    const endpoint = fields[1]?.match(/^(.*):(\d+)$/);
    if (!endpoint || fields.length !== 5) throw new Error('Cannot verify Windows TCP connection table');
    const address = endpoint[1];
    const family = address.startsWith('[') ? 'ipv6' : 'ipv4';
    const range = ranges[family];
    if (!range) throw new Error('Missing Windows TCP dynamic port range');
    const port = Number(endpoint[2]);
    // A socket can keep its slot while its process exits. Include all states
    // and deduplicate shared local endpoints rather than counting connections.
    if (port < range.start || port >= range.start + range.count) continue;
    if (!addresses.has(address)) addresses.set(address, { family, ports: new Set() });
    addresses.get(address).ports.add(port);
  }
  if (!rows) throw new Error('Cannot verify empty Windows TCP connection table');
  const groups = [...addresses.values()].map(({ family, ports }) => {
    const capacity = ranges[family].count;
    const used = ports.size;
    const reserve = Math.min(2048, Math.ceil(capacity / 8));
    return { family, used, capacity, remaining: capacity - used, reserve,
      blocked: capacity - used < reserve };
  });
  return { blocked: groups.some(group => group.blocked), groups };
}

export async function inspectWindowsNetwork({ exec = execute, timeoutMs = 30_000 } = {}) {
  const deadline = performance.now() + timeoutMs;
  const inspectCommand = (exe, args) => {
    const remaining = Math.ceil(deadline - performance.now());
    if (remaining <= 0) throw new Error('Windows TCP inspection exceeded its deadline');
    return exec(exe, args, { encoding: 'utf8', windowsHide: true,
      timeout: remaining, maxBuffer: 16 * 1024 * 1024 });
  };
  const ranges = {};
  for (const family of ['ipv4', 'ipv6']) {
    const { stdout } = await inspectCommand('netsh.exe', ['int', family, 'show', 'dynamicport', 'tcp']);
    ranges[family] = parseDynamicPorts(stdout);
  }
  // Omitting -p includes TCPv6 as well as TCPv4; UDP lines are ignored above.
  const { stdout } = await inspectCommand('netstat.exe', ['-ano']);
  return summarizePortPressure(stdout, ranges);
}

const currentJstDate = () => new Intl.DateTimeFormat('en-CA', {
  timeZone: 'Asia/Tokyo', year: 'numeric', month: '2-digit', day: '2-digit',
}).format(new Date());

export async function waitForNetworkCapacity({
  platform = process.platform, inspect = inspectWindowsNetwork,
  timeoutMs = 900_000, pollMs = 30_000, expectedDate,
  currentDate = currentJstDate, now = () => performance.now(),
  sleep = ms => new Promise(resolve => setTimeout(resolve, ms)), onProgress = () => {},
} = {}) {
  if (!Number.isInteger(timeoutMs) || timeoutMs < 0 || timeoutMs > 1_800_000 ||
      !Number.isInteger(pollMs) || pollMs < 1 || pollMs > 60_000) {
    throw new Error('Invalid bounded Cloud network wait');
  }
  if (platform !== 'win32') return { skipped: 'non_windows' };
  const started = now();
  for (;;) {
    if (expectedDate && currentDate() !== expectedDate) {
      throw new Error('Cloud network wait crossed its JST run date; no acquisition started');
    }
    // timeoutMs=0 requests one bounded inspection without waiting. Otherwise
    // the same budget includes inspection time, not only polling sleeps.
    const remainingMs = timeoutMs - Math.max(0, now() - started);
    if (timeoutMs > 0 && remainingMs < 0) throw new Error('Cloud network wait exceeded its deadline; no acquisition started');
    const snapshot = await inspect({ timeoutMs: timeoutMs === 0 ? 30_000 : Math.min(30_000, Math.max(1, remainingMs)) });
    const elapsedMs = Math.max(0, now() - started);
    if (expectedDate && currentDate() !== expectedDate) {
      throw new Error('Cloud network wait crossed its JST run date; no acquisition started');
    }
    if (timeoutMs > 0 && elapsedMs > timeoutMs) {
      throw new Error('Cloud network wait exceeded its deadline; no acquisition started');
    }
    await onProgress({ ...snapshot, elapsedMs, status: snapshot.blocked ? 'waiting' : 'ready' });
    if (!snapshot.blocked) return { ...snapshot, waitedMs: elapsedMs };
    if (elapsedMs >= timeoutMs) {
      throw Object.assign(new Error('Windows TCP ports remain exhausted; release the owning application or restart Windows before resuming this stage'),
        { failureType: 'windows_tcp_ports_exhausted' });
    }
    await sleep(Math.min(pollMs, timeoutMs - elapsedMs));
  }
}
