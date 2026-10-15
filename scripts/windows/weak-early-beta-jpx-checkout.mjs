import fs from 'node:fs';
import path from 'node:path';
import { isDeepStrictEqual } from 'node:util';

export const JPX_SNAPSHOT = 'weak_early_beta/state/jpx_restricted_symbols_latest.json';
const BRANCH = 'research/weak-early-beta';
const REF = `origin/${BRANCH}`;
const SHA = /^[a-f0-9]{64}$/;

function snapshot(raw) {
  const value = JSON.parse(raw);
  if (value.version !== 2 || !/^\d{4}-\d{2}-\d{2}$/.test(value.as_of ?? '') ||
      !Number.isFinite(Date.parse(value.as_of)) ||
      !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?\+09:00$/.test(value.fetched_at ?? '') ||
      !Number.isFinite(Date.parse(value.fetched_at)) || value.fetched_at.slice(0, 10) < value.as_of ||
      value.source_url !== 'https://www.jpx.co.jp/listing/market-alerts/supervision/01.html' ||
      !SHA.test(value.source_sha256 ?? '')) throw new Error('invalid JPX snapshot metadata');
  for (const key of ['symbols', 'delisted_symbols', 'delisting_history', 'relisted_symbols', 'delisting_sources', 'relisting_sources']) {
    if (!Array.isArray(value[key])) throw new Error('invalid JPX snapshot arrays');
  }
  for (const source of [...value.delisting_sources, ...value.relisting_sources]) {
    if (!SHA.test(source.source_sha256 ?? '') || !/^https:\/\/www\.jpx\.co\.jp\/listing\/stocks\/(?:new|delisted)\/(?:index|(?:00-)?archives-\d{2})\.html$/.test(source.source_url ?? '')) {
      throw new Error('invalid JPX snapshot source');
    }
  }
  return value;
}

function data(value) {
  const copy = structuredClone(value);
  for (const key of ['as_of', 'fetched_at', 'source_sha256']) delete copy[key];
  for (const source of [...copy.delisting_sources, ...copy.relisting_sources]) delete source.source_sha256;
  return copy;
}

export function assertMetadataRefresh(beforeRaw, afterRaw) {
  const before = snapshot(beforeRaw), after = snapshot(afterRaw);
  if (!isDeepStrictEqual(data(before), data(after))) throw new Error('JPX symbol data or rules changed; manual review required');
  if (after.as_of < before.as_of || Date.parse(after.fetched_at) < Date.parse(before.fetched_at)) {
    throw new Error('JPX refresh predates the saved snapshot');
  }
  return after;
}

const status = async git => (await git(['status', '--porcelain=v1', '-z', '--untracked-files=all'])).stdout;
const text = async (git, args) => (await git(args)).stdout.trim();

function requireOnlySnapshot(value, staged = false) {
  if (value !== `${staged ? 'M ' : ' M'} ${JPX_SNAPSHOT}\0`) throw new Error('unexpected checkout changes; JPX-only repair refused');
}

async function requireContext(git, checkSafety, expectedHead) {
  await checkSafety();
  if (await text(git, ['branch', '--show-current']) !== BRANCH) throw new Error('JPX repair requires research/weak-early-beta');
  if (!/^(?:https:\/\/github\.com\/|git@github\.com:)Ken5InvestmentLab\/screening-bot(?:\.git)?$/i.test(await text(git, ['remote', 'get-url', 'origin']))) {
    throw new Error('unexpected JPX repair origin');
  }
  const head = await text(git, ['rev-parse', 'HEAD']);
  if (!/^[a-f0-9]{40}$/.test(head) || (expectedHead && head !== expectedHead)) throw new Error('JPX repair HEAD changed');
  return head;
}

async function requireLiveHead(git, head) {
  const remote = await text(git, ['ls-remote', '--exit-code', 'origin', `refs/heads/${BRANCH}`]);
  if (remote !== `${head}\trefs/heads/${BRANCH}`) throw new Error('JPX repair remote advanced; refusing commit or push');
}

async function commitSnapshot({ repo, git, checkSafety, startCommit, raw, date }) {
  await requireContext(git, checkSafety, startCommit);
  await requireLiveHead(git, startCommit);
  requireOnlySnapshot(await status(git));
  if (fs.readFileSync(path.join(repo, JPX_SNAPSHOT), 'utf8') !== raw) throw new Error('JPX snapshot changed during repair');
  await git(['add', '--', JPX_SNAPSHOT]);
  const staged = await text(git, ['diff', '--cached', '--name-only', '-z']);
  if (staged !== `${JPX_SNAPSHOT}\0`) throw new Error('unexpected JPX staged paths');
  requireOnlySnapshot(await status(git), true);
  if (!isDeepStrictEqual(JSON.parse((await git(['show', `:${JPX_SNAPSHOT}`])).stdout), JSON.parse(raw))) {
    throw new Error('staged JPX snapshot differs from audited refresh');
  }
  await requireContext(git, checkSafety, startCommit);
  await requireLiveHead(git, startCommit);
  await git(['commit', '-m', `chore: preserve Cloud JPX refresh ${date} [skip ci]`]);
  const commit = await requireContext(git, checkSafety);
  if (await text(git, ['rev-parse', 'HEAD^']) !== startCommit ||
      (await git(['diff-tree', '--no-commit-id', '--name-only', '-r', '-z', 'HEAD'])).stdout !== `${JPX_SNAPSHOT}\0` ||
      await status(git)) throw new Error('JPX commit contains unexpected changes; push refused');
  await requireLiveHead(git, startCommit);
  await git(['push', 'origin', `${commit}:refs/heads/${BRANCH}`]);
  await requireLiveHead(git, commit);
  return { committed: true, commit, paths: [JPX_SNAPSHOT] };
}

// Called only after acquiring the reminder lock and checking other runners.
// Unknown files and actual symbol/rule edits never enter this repair path.
export async function prepareJpxCheckout({ repo, git, checkSafety, auditDir }) {
  const head = await requireContext(git, checkSafety);
  const initialStatus = await status(git);
  let raw, candidate;
  if (initialStatus) {
    requireOnlySnapshot(initialStatus);
    const file = path.join(repo, JPX_SNAPSHOT);
    if (fs.lstatSync(file).isSymbolicLink()) throw new Error('JPX snapshot cannot be a symlink');
    raw = fs.readFileSync(file, 'utf8');
    candidate = assertMetadataRefresh((await git(['show', `HEAD:${JPX_SNAPSHOT}`])).stdout, raw);
  }
  await git(['fetch', 'origin', BRANCH]);
  await git(['merge-base', '--is-ancestor', head, REF]);
  const remoteHead = await text(git, ['rev-parse', REF]);
  await requireLiveHead(git, remoteHead);
  let action = 'clean';
  if (candidate) {
    const remote = snapshot((await git(['show', `${REF}:${JPX_SNAPSHOT}`])).stdout);
    if (remote.as_of >= candidate.as_of && Date.parse(remote.fetched_at) >= Date.parse(candidate.fetched_at)) action = 'superseded';
    else {
      if (candidate.as_of < remote.as_of || Date.parse(candidate.fetched_at) < Date.parse(remote.fetched_at) ||
          !isDeepStrictEqual(data(candidate), data(remote))) throw new Error('conflicting JPX snapshots; preserving local change');
      action = 'preserve';
    }
    await requireContext(git, checkSafety, head);
    if (await status(git) !== initialStatus || fs.readFileSync(path.join(repo, JPX_SNAPSHOT), 'utf8') !== raw) {
      throw new Error('checkout changed during JPX inspection');
    }
    fs.mkdirSync(auditDir, { recursive: true });
    fs.writeFileSync(path.join(auditDir, 'jpx-before.json'), raw, { flag: 'wx' });
    await git(['restore', '--source=HEAD', '--worktree', '--', JPX_SNAPSHOT]);
  }
  try {
    await requireContext(git, checkSafety, head);
    if (await status(git)) throw new Error('checkout changed before fast-forward');
    await requireLiveHead(git, remoteHead);
    await git(['merge', '--ff-only', REF]);
    await requireContext(git, checkSafety, remoteHead);
    if (await status(git)) throw new Error('checkout changed during fast-forward');
  } catch (error) {
    // Do not strand a needed refresh only in an ignored audit file when the
    // fast-forward fails. Restore it only while the same checkout stays clean.
    if (action === 'preserve') {
      try {
        const currentHead = await requireContext(git, checkSafety);
        if ([head, remoteHead].includes(currentHead) && !await status(git)) {
          fs.writeFileSync(path.join(repo, JPX_SNAPSHOT), raw);
        }
      } catch { /* The original bytes remain in jpx-before.json for audit. */ }
    }
    throw error;
  }
  let receipt = { committed: false };
  if (action === 'preserve') {
    fs.writeFileSync(path.join(repo, JPX_SNAPSHOT), raw);
    receipt = await commitSnapshot({ repo, git, checkSafety, startCommit: remoteHead, raw, date: candidate.as_of });
  }
  await requireContext(git, checkSafety);
  if (await status(git)) throw new Error('JPX checkout repair did not finish cleanly');
  const finalCommit = await text(git, ['rev-parse', 'HEAD']);
  await requireLiveHead(git, finalCommit);
  return { action, ...receipt, finalCommit };
}

// A failed detector may have refreshed only source metadata before failing.
// Preserve that completed refresh immediately instead of blocking tomorrow.
export async function checkpointJpxRefresh({ repo, git, checkSafety, startedAt, date, startCommit }) {
  const currentStatus = await status(git);
  if (!currentStatus) return { committed: false };
  requireOnlySnapshot(currentStatus);
  await requireContext(git, checkSafety, startCommit);
  if (!/^[a-f0-9]{40}$/.test(startCommit ?? '')) throw new Error('missing frozen detection HEAD');
  if (fs.lstatSync(path.join(repo, JPX_SNAPSHOT)).isSymbolicLink()) throw new Error('JPX snapshot cannot be a symlink');
  const raw = fs.readFileSync(path.join(repo, JPX_SNAPSHOT), 'utf8');
  const current = assertMetadataRefresh((await git(['show', `HEAD:${JPX_SNAPSHOT}`])).stdout, raw);
  if (current.as_of !== date || Date.parse(current.fetched_at) < Date.parse(startedAt) || Date.parse(current.fetched_at) > Date.now()) {
    throw new Error('JPX refresh is not from this failed detection');
  }
  return commitSnapshot({ repo, git, checkSafety, startCommit, raw, date });
}
