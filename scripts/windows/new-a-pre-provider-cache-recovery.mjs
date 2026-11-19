import fs from 'node:fs';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { isDeepStrictEqual } from 'node:util';
import { jstDay } from './weak-early-beta-run-journal.mjs';

const CACHE_MEMORY_FAILURE = {
  identity: 'NEW_A_PRE_PROVIDER_CACHE_FAILURE_V1', reason: 'memory', phase: 'previous-cache-read',
};
const SHA256 = /^[a-f0-9]{64}$/;
const RUN_TIME = /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z$/;
const INVOCATION = /^\d{4}-\d\d-\d\dT\d\d-\d\d-\d\d-\d{3}Z-[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/;
const digest = bytes => createHash('sha256').update(bytes).digest('hex');
const parse = bytes => JSON.parse(bytes.toString('utf8').replace(/^\uFEFF/, ''));

function readLocalFile(file, maxBytes) {
  const stat = fs.lstatSync(file);
  if (!stat.isFile() || stat.size > maxBytes || fs.realpathSync(file) !== path.resolve(file)) {
    throw new Error('Unavailable bounded local detection evidence');
  }
  const bytes = fs.readFileSync(file);
  if (bytes.byteLength !== stat.size || fs.statSync(file).mtimeMs !== stat.mtimeMs) {
    throw new Error('Detection evidence changed while reading');
  }
  return bytes;
}

function assertNoArchive(file) {
  try { fs.lstatSync(file); } catch (error) { if (error.code === 'ENOENT') return; throw error; }
  throw new Error('Acquisition archive already exists or has an ambiguous owner');
}

function attemptEvidence(runtime, result, sourceSha256) {
  if (!RUN_TIME.test(result.startedAt) || !Number.isFinite(Date.parse(result.startedAt))
    || jstDay(new Date(result.startedAt)) !== result.date || !SHA256.test(sourceSha256)
    || !Number.isSafeInteger(result.pid) || result.pid <= 0
    || result.identity !== 'WEAK_EARLY_CLOUD_DAILY_V1' || result.ok !== false || result.stage !== 'detection'
    || result.originalRunId || result.delayedClaim || result.nativeAdmissionContinuation || result.deployment
    || result.notifications || result.notificationPreview || result.notificationReconciliation
    || result.fundamentals?.length || result.latestSession || result.selectorRows !== undefined
    || result.new_a?.entry !== 'new-a-verified-daily-v1' || result.new_a.strategy !== 'A_BASE'
    || result.new_a.owner_publication_verified !== false
    || !/^[a-f0-9]{40}$/.test(result.startCommit)
    || result.approvedWorkerPreflight?.sourceCommit !== result.startCommit) {
    throw new Error('Only an initial ordinary New A failure may recover before acquisition');
  }
  const run = path.resolve(runtime, 'daily-' + result.startedAt.replace(/[:.]/g, '-'));
  if (!fs.lstatSync(run).isDirectory() || fs.realpathSync(run) !== run) {
    throw new Error('Original detection directory differs');
  }
  const archive = path.join(run, 'acquisition-1');
  if (!isDeepStrictEqual(result.acquisitionEvidence, [{ attempt: 1, directory: archive }])) {
    throw new Error('Original acquisition is not the exact first attempt');
  }
  const { child, childReceiptSha256, stderrSha256 } = readFailedDetectionAttempt(run, result);
  return { run, child, proof: {
    schema: 'CLOUD_ORDINARY_PRE_PROVIDER_FAILURE_V1', sourceSha256, childReceiptSha256, stderrSha256,
  } };
}

function readFailedDetectionAttempt(run, result) {
  assertNoArchive(path.join(run, 'acquisition-1'));
  const bytes = readLocalFile(path.join(run, 'detect-1.process.json'), 4096);
  const child = parse(bytes);
  const exited = Date.parse(child.completedAt);
  if (child.identity !== 'CLOUD_CHILD_PROCESS_V1' || child.status !== 'exited' || child.code !== 1
    || !Number.isSafeInteger(child.pid) || child.pid <= 0 || child.pid === result.pid
    || !Number.isFinite(exited) || exited < Date.parse(result.startedAt)) {
    throw new Error('Exact terminal detection child is unconfirmed');
  }
  const stderr = readLocalFile(path.join(run, 'detect-1.stderr'), 131_072);
  const lines = stderr.toString('utf8').split(/\r?\n/);
  const markers = lines.flatMap(line => {
    if (!line.startsWith('{')) return [];
    try { return [JSON.parse(line)]; } catch { return []; }
  }).filter(event => event?.identity === CACHE_MEMORY_FAILURE.identity);
  if (markers.length !== 1 || !isDeepStrictEqual(markers[0], CACHE_MEMORY_FAILURE)) {
    throw new Error('Exact previous-cache memory failure marker is unavailable');
  }
  return { child, childReceiptSha256: digest(bytes), stderrSha256: digest(stderr) };
}

export function repeatedPreProviderCacheFailure(run, result) {
  try { readFailedDetectionAttempt(run, result); return true; } catch { return false; }
}

// Evidence capture must never replace the original failure or make a retry eligible
// when the child output or archive state cannot be read.
export function capturePreProviderCacheFailure(runtime, result, sourceSha256) {
  try { return attemptEvidence(runtime, result, sourceSha256).proof; } catch { return null; }
}

export function verifyPreProviderCacheRecovery(runtime, prior, sourceSha256, resumeReceipt) {
  const { run, child, proof } = attemptEvidence(runtime, prior, sourceSha256);
  const completed = Date.parse(prior.completedAt);
  if (!Number.isFinite(completed) || completed < Date.parse(child.completedAt)
    || prior.privateSourceCacheRetained !== true || !isDeepStrictEqual(prior.preProviderCacheFailure, proof)
    || !isDeepStrictEqual(parse(readLocalFile(path.join(run, 'result.json'), 262_144)), prior)) {
    throw new Error('Original terminal pre-provider failure proof differs; reconcile before retrying');
  }
  if (resumeReceipt) {
    const key = prior.startedAt.replace(/[^0-9TZ-]/g, '');
    if (path.resolve(resumeReceipt) !== path.resolve(runtime, `recovery-input-${key}.json`)) {
      throw new Error('Pre-provider recovery requires the exact task-entry receipt');
    }
    const claim = parse(readLocalFile(path.join(runtime, `recovery-${key}.json`), 4096));
    if (claim.priorStartedAt !== prior.startedAt || !INVOCATION.test(claim.invocation)
      || claim.preProviderSourceSha256 !== sourceSha256) {
      throw new Error('Pre-provider recovery requires the exact one-shot task-entry claim');
    }
  }
  return proof;
}
