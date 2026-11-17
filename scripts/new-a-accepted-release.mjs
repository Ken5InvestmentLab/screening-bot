// No production adapters or CLI. Used by the isolated CI/runtime handoff tests.
// The existing wrangler deploy command IS NOT a stage-only adapter.
import {createHash} from 'node:crypto';
import fs from 'node:fs';
import {guardedDeploy} from '../weak-early-beta-gate/scripts/deploy-with-provider-recovery.mjs';

const stable = value => JSON.stringify(value, (_key, item) => item && typeof item === 'object' && !Array.isArray(item)
  ? Object.fromEntries(Object.entries(item).sort(([a], [b]) => a.localeCompare(b))) : item);
export const pairDigest = value => createHash('sha256').update(stable(value)).digest('hex');
const same = (a, b) => stable(a) === stable(b);
const sha = value => /^[a-f0-9]{64}$/.test(value || '');
const commit = value => /^[a-f0-9]{40}$/.test(value || '');
function requireState(condition, code) {if (!condition) throw Error(code);}

function checkedBinding(binding, expected, now) {
  requireState(binding?.schema === 'NEW_A_RELEASE_CANDIDATE_BINDING_V1' &&
    commit(binding.source_commit) && binding.source_commit === expected.source_commit &&
    same(binding.target, expected.target) && binding.target.service === 'tentei-kyokuchi-cloud' &&
    binding.target.binding === 'CLOUD_DB' && binding.target.database_name === 'tentei-cloud-settings' &&
    binding.evidence_mode === 'PRIVATE_PRETRAFFIC_PROBE' &&
    /^[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12}$/.test(binding.worker_version_id || '') &&
    ['acceptance_sha256', 'activation_sha256', 'preparation_sha256'].every(k => sha(binding[k])) &&
    binding.platform_signature_claimed === false && Number.isFinite(Date.parse(binding.not_after)) &&
    now() < Date.parse(binding.not_after), 'EXACT_PRIVATE_CANDIDATE_ACCEPTANCE_REQUIRED');
  return binding;
}

function candidatePair(binding, repository) {
  requireState(typeof repository === 'string' && repository.length > 0, 'CANDIDATE_REPOSITORY_REQUIRED');
  return {schema: 'NEW_A_OPERATING_ACCEPTED_PAIR_V1', source_commit: binding.source_commit,
    worker_version_id: binding.worker_version_id, target: binding.target,
    acceptance_sha256: binding.acceptance_sha256, activation_sha256: binding.activation_sha256,
    repository};
}

// Contract of the missing real adapter: an existing protected, nonpublic
// candidate proof and a serialized CAS selection of the whole accepted pair.
// A self-authored receipt or a claimed capability is not authority: the host
// must supply independently verified functions. There is no file/env fallback.
export async function coordinateAcceptedRelease({expected, candidateRepository, verifyCandidate,
  verifyPair, backend, ci, now = Date.now, audit = () => {}}) {
  requireState(backend?.capability === 'PRIVATE_CANDIDATE_AND_ACCEPTED_PAIR_CAS_V1' &&
    ['acquire', 'release', 'readPair', 'selectPair', 'readSelection'].every(k => typeof backend[k] === 'function') &&
    typeof verifyCandidate === 'function' && typeof verifyPair === 'function' &&
    ci?.stageOnly === true && typeof ci.runDeploy === 'function' && typeof ci.assertHead === 'function',
    'FORMAL_PRETRAFFIC_HANDOFF_ADAPTER_UNAVAILABLE');
  const lease = await backend.acquire();
  let before, proposed, attemptedSelection = false, selectionResolved = false, preserveLease = false;
  let stageAttempted = false, stageReadbackConfirmed = false;
  const save = (phase, fields = {}) => audit({phase, at: new Date(now()).toISOString(), ...fields});
  try {
    before = await backend.readPair();
    requireState(await verifyPair(before) === true, 'CURRENT_ACCEPTED_PAIR_INVALID');
    const initial = checkedBinding(await verifyCandidate(), expected, now);
    proposed = candidatePair(initial, candidateRepository);
    requireState(initial.source_commit !== before.source_commit && same(initial.target, before.target),
      'DISTINCT_SAME_TARGET_UPGRADE_REQUIRED');
    const check = async () => {
      const current = checkedBinding(await verifyCandidate(), expected, now);
      requireState(same(current, initial), 'CANDIDATE_ACCEPTANCE_CHANGED');
      if (!same(await backend.readPair(), before)) {
        preserveLease = true;
        throw Error('OPERATING_PAIR_CHANGED');
      }
      requireState(await verifyPair(before) === true, 'CURRENT_ACCEPTANCE_REVOKED_OR_CHANGED');
    };
    save('candidate-verified', {source_commit: initial.source_commit,
      before_pair_sha256: pairDigest(before), proposed_pair_sha256: pairDigest(proposed)});
    // Keep all existing latest-HEAD, source/asset pin and provider retry checks.
    // Only a real stage-only adapter can enter this wrapper; never substitute
    // the current traffic-changing runDeploy implementation from main().
    const result = await guardedDeploy({...ci, now, runDeploy: async () => {
      stageAttempted = true;
      return ci.runDeploy();
    }, assertHead: async () => {
      await ci.assertHead(); await check();
    }});
    if (!same(await backend.readPair(), before)) {
      preserveLease = true;
      throw Error('STAGE_CHANGED_LIVE_PAIR_RECONCILE');
    }
    stageReadbackConfirmed = true;
    if (!result.ok) {
      save('stage-failed-old-retained');
      return {status: 'old-retained', stage: result, selected: before, starts: 0, notifications: 0};
    }
    await check();
    save('selection-started');
    attemptedSelection = true;
    let acknowledged = true;
    try {await backend.selectPair({expectedDigest: pairDigest(before), proposed, lease});}
    catch {acknowledged = false;} // Outcome is determined ONLY by readback.
    const actual = await backend.readPair();
    const operation = await backend.readSelection(lease);
    if (same(actual, proposed) && operation?.state === 'COMMITTED' &&
        operation.pairDigest === pairDigest(proposed)) {
      requireState(await verifyPair(actual) === true, 'SELECTED_ACCEPTANCE_INVALID_RECONCILE');
      selectionResolved = true;
      save('selected-readback', {acknowledged});
      return {status: 'selected', selected: actual, acknowledged, starts: 0, notifications: 0};
    }
    if (same(actual, before) && operation?.state === 'NOT_COMMITTED') {
      selectionResolved = true;
      save('selection-not-committed-old-retained');
      return {status: 'old-retained', selected: before, acknowledged, starts: 0, notifications: 0};
    }
    throw Error('SELECTION_OUTCOME_UNKNOWN_RECONCILE');
  } catch (error) {
    save('blocked', {code: String(error.message).match(/^[A-Z_]+$/)?.[0] || 'CHECK_FAILED', attemptedSelection});
    // Never publish again, roll back, overwrite a concurrent selection, clear
    // another lease, launch a runner or send notifications after an ambiguity.
    throw error;
  } finally {
    if (preserveLease || (stageAttempted && !stageReadbackConfirmed) ||
        (attemptedSelection && !selectionResolved)) save('lease-preserved-reconcile');
    else await backend.release(lease);
  }
}

// Adapter boundary immediately before the ordinary task-entry launch checks.
// It does not replace launchPreflight or requireRemoteHead, and never spawns.
export async function acceptedLaunchPreflight({readPair, verifyPair, normalPreflight,
  requireLatestHead, releaseInProgress}) {
  requireState([readPair, verifyPair, normalPreflight, requireLatestHead, releaseInProgress]
    .every(f => typeof f === 'function'), 'NORMAL_LAUNCH_READERS_REQUIRED');
  requireState(await releaseInProgress() === false, 'RELEASE_HANDOFF_IN_PROGRESS');
  const selected = await readPair();
  requireState(await verifyPair(selected) === true, 'SELECTED_ACCEPTANCE_INVALID');
  const ready = await normalPreflight(selected);
  requireState(ready?.ok === true && ready.head === selected.source_commit &&
    fs.realpathSync.native(ready.repository) === fs.realpathSync.native(selected.repository),
    'NORMAL_PREFLIGHT_SOURCE_OR_REPOSITORY_MISMATCH');
  requireState(await requireLatestHead(selected) === selected.source_commit, 'LATEST_RESEARCH_HEAD_REQUIRED');
  requireState(await releaseInProgress() === false && same(await readPair(), selected) &&
    await verifyPair(selected) === true, 'SELECTION_CHANGED_BEFORE_LAUNCH');
  return {...ready, accepted_pair_sha256: pairDigest(selected), starts: 0};
}
