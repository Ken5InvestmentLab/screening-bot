import fs from 'node:fs';
import path from 'node:path';
import { randomUUID, createHash } from 'node:crypto';

// Small durable records are independent of streamed console output/session IDs.
export function atomicJson(file, value) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  const temporary = `${file}.${randomUUID()}.tmp`;
  const fd = fs.openSync(temporary, 'wx');
  try { fs.writeFileSync(fd, JSON.stringify(value, null, 2) + '\n'); fs.fsyncSync(fd); }
  finally { fs.closeSync(fd); }
  fs.renameSync(temporary, file);
}

export function appendEvent(file, event) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  const fd = fs.openSync(file, 'a');
  try { fs.writeFileSync(fd, JSON.stringify(event) + '\n'); fs.fsyncSync(fd); }
  finally { fs.closeSync(fd); }
}

export function readRecord(file) {
  return JSON.parse(fs.readFileSync(file, 'utf8').replace(/^\uFEFF/, ''));
}

export function jstDay(now = new Date()) {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Tokyo', year: 'numeric', month: '2-digit', day: '2-digit' }).format(now);
}

export function startInvocation(directory, { task, configPath, now = new Date() }) {
  if (!['cloud-2', 'cloud-3', 'cloud-5'].includes(task)) throw new Error('Unexpected Cloud task');
  const id = `${now.toISOString().replace(/[:.]/g, '-')}-${randomUUID()}`;
  const file = path.join(directory, `${task}-${jstDay(now)}-${id}.json`);
  const value = { identity: 'CLOUD_TASK_INVOCATION_V1', id, task, date: jstDay(now), startedAt: now.toISOString(),
    pid: process.pid, configPath: path.resolve(configPath), status: 'invoked' };
  atomicJson(file, value);
  return { file, value, update(extra) { Object.assign(value, extra, { updatedAt: new Date().toISOString() }); atomicJson(file, value); return value; } };
}

// Unknown includes denied/timed-out inspection, never permission to launch.
export function classifyPreflight(error) {
  const message = String(error?.message || error);
  const abnormal = /Unexpected Cloud (?:branch|origin|Worker)|not clean|lock exists|already active|another repository|escapes|outside|repository mismatch|does not match its stable source-quality|Required Cloud runtime/i;
  return { status: abnormal.test(message) ? 'abnormal' : 'unknown', reason: message.slice(0, 1000) };
}

export async function boundedPreflight(check, { attempts = 3, delayMs = 30_000, wait = ms => new Promise(r => setTimeout(r, ms)),
  date = jstDay(), today = () => jstDay(), onAttempt = () => {} } = {}) {
  if (!Number.isInteger(attempts) || attempts < 1 || attempts > 3 || delayMs < 0 || delayMs > 60_000) throw new Error('Invalid bounded preflight policy');
  for (let attempt = 1; attempt <= attempts; attempt++) {
    if (today() !== date) return { status: 'abnormal', reason: 'JST target date changed', attempt };
    let outcome;
    try { const result = await check(); outcome = result?.ok === true ? { status: 'ready', result } : { status: 'unknown', reason: 'No affirmative readiness result' }; }
    catch (error) { outcome = classifyPreflight(error); }
    onAttempt({ ...outcome, attempt });
    if (outcome.status !== 'unknown' || attempt === attempts) return { ...outcome, attempt };
    await wait(delayMs);
  }
}

export async function fileSha(file) {
  const hash = createHash('sha256');
  for await (const chunk of fs.createReadStream(file)) hash.update(chunk);
  return hash.digest('hex');
}

export async function verifiedDetectionCache(repo, date) {
  const source = path.join(repo, '.cache', 'weak_early_beta', 'tse_daily.csv');
  const receipt = readRecord(source.replace(/\.csv$/, '.source-quality.json'));
  const before = fs.statSync(source), sha = await fileSha(source), after = fs.statSync(source);
  if (receipt.identity !== 'CLOUD_SOURCE_QUALITY_V1' || receipt.daily_sha256 !== sha || before.size !== after.size || before.mtimeMs !== after.mtimeMs) throw new Error('Detection recovery cache is not stable and verified');
  // Full semantic/causal validation is still run by Python; the wrapper never edits prices.
  return { date, source, sha256: sha };
}

export function recoveryPlan(prior, date) {
  if (!prior || prior.identity !== 'WEAK_EARLY_CLOUD_DAILY_V1' || prior.date !== date) return { action: 'none', reason: 'No same-day runner receipt' };
  if (prior.ok === true) return { action: 'complete' };
  if (!prior.completedAt) return { action: 'observe', reason: 'Existing run not terminal' };
  // Never blindly replay publication/send/Git stages, whose outcome may be ambiguous.
  if (prior.stage === 'detection' && !prior.deployment && !prior.notifications && !prior.fundamentals?.length) return { action: 'resume-detection' };
  return { action: 'reconcile', reason: `Stage ${prior.stage || 'unknown'} requires artifact/receipt reconciliation` };
}
