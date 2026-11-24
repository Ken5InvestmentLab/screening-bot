"""Formally reaccept ordinary operation after a completed finite recovery.

Preparation is read-only. Applying a separately issued ordinary grant changes
only activation and its audit. The trusted host must provide the actual primary
message, exact normal Worker observations and terminal recovery readback.
"""
from pathlib import Path
import datetime
import hashlib
import json
import os
import re
import sys

from . import continuing_acceptance as ca
from . import operational_admission as finite
from . import release_acceptance as release
from .approval_git import approval_blobs
from .files import atomic_write, digest, encode, file_sha, private_root, read


DECISION = 'CONTINUING_DAILY_AFTER_FINITE_RECOVERY_AUTH_REVIEW'
CLOSURE_SCHEMA = 'NEW_A_VERIFIED_FINITE_COMPLETION_V1'
PREPARATION_SCHEMA = 'NEW_A_CONTINUING_TRANSITION_PREPARATION_V1'
APPLICATION_SCHEMA = ca.TRANSITION_APPLICATION_SCHEMA
RUNTIME_RELEASE_SCHEMA = 'NEW_A_ORDINARY_RUNTIME_RELEASE_V1'


def checked_normal_deployment(source, target, reader):
    value = release.checked_deployment(source, target, reader)
    ca.require(value['schema'] == 'NEW_A_HOST_VERIFIED_DEPLOYMENT_V1',
               'transition requires the actual normal deployed Worker version')
    ca.require(all(re.fullmatch(r'[a-f0-9]{64}', str(value.get(key, '')))
                   for key in ('build_input_sha256', 'policy_sha256'))
               and type(value.get('ci_run_id')) is int and value['ci_run_id'] > 0
               and re.fullmatch(r'cloud-deploy-[A-Za-z0-9._-]{1,100}', str(value.get('tag', ''))),
               'normal deployment build, policy or workflow identity unavailable')
    return value


def same_normal_deployment(first, latest):
    return release.same_deployment(first, latest) and all(
        first[key] == latest[key] for key in ('build_input_sha256', 'policy_sha256', 'ci_run_id', 'tag')
    )


def baseline(repo, plan, *, archived_activation=None):
    """Bind active overlay bytes to the exact accepted historical predecessor."""
    repo = Path(repo).resolve()
    activation_path = archived_activation or (private_root(repo) / 'activation.json')
    expected_sha = plan['expected_activation_sha256']
    current = read(activation_path)
    ca.require(file_sha(activation_path) == expected_sha,
               'activation baseline changed before transition preparation')
    ca.require(current.get('schema') == 'NEW_A_OWNER_ACTIVATION_V1'
               and current.get('active') is True
               and current.get('external_actions_approved') is True
               and current.get('strategy') == 'A_BASE',
               'active recovery baseline is unavailable')
    previous = plan['prior_acceptance']
    finite_ref = plan['finite_admission']
    ca.require(isinstance(previous, dict) and isinstance(finite_ref, dict)
               and current.get('operational_admission') == finite_ref
               and current.get('owner_acceptance', {}).get('continuing_acceptance') == previous,
               'active finite recovery or continuing predecessor differs')

    record_path, record = finite.load_ref(repo, finite_ref)
    ca.require(record.get('schema') == finite.SCHEMA
               and record.get('scope') == 'FINITE_NOV17_NATIVE_ONCE_WITH_PREDEPLOYED_CODE_ONLY_WORKER'
               and record.get('target_date') == finite.TARGET
               and record.get('execution_date') == finite.EXECUTION
               and record.get('target') == plan['target']
               and record.get('strategy') == 'A_BASE'
               and isinstance(record.get('source_commit'), str)
               and re.fullmatch(r'[a-f0-9]{40}', record['source_commit'])
               and record.get('owner_http_observed') is False
               and record.get('authenticated_nonowner_observed') is False
               and record.get('platform_signature_claimed') is False,
               'historical finite scope differs')
    original_path = record_path.parent / 'original-activation.json'
    ca.require(not original_path.is_symlink()
               and file_sha(original_path) == record['original_activation_sha256'],
               'historical activation backup differs')
    original = read(original_path)
    without_finite = {key: value for key, value in current.items() if key != 'operational_admission'}
    ca.require(without_finite == original, 'finite overlay changed the historical activation')
    old_path, old = ca.load_reference(repo, previous, 'records')
    ca.require(old.get('schema') == ca.SCHEMA
               and old.get('target') == plan['target']
               and old.get('source_commit') != plan['source_commit'],
               'historical V1 predecessor or target differs')
    old_application = original['owner_acceptance'].get('application_id')
    ca.require(isinstance(old_application, str) and re.fullmatch(r'[a-f0-9]{64}', old_application),
               'historical initial application identity differs')
    old_completion = ca.root(repo) / 'applications' / old_application / 'completed.json'
    ca.require(read(old_completion).get('schema') == 'NEW_A_CONTINUING_ACCEPTANCE_APPLICATION_V1',
               'finite recovery predecessor was not an ordinary continuing application')
    historical = finite.historical_review(repo, original, activation_path=original_path)
    ca.require(historical == record.get('historical_acceptance'),
               'historical acceptance audit differs from original finite record')
    return dict(activation_path=activation_path, activation_sha256=expected_sha,
                finite_path=record_path, finite_record=record, original_path=original_path,
                original_sha256=record['original_activation_sha256'], old_path=old_path,
                previous_record=old, historical=historical)


def validate_closure(closure, finite_ref, record):
    ca.require(isinstance(closure, dict)
               and closure.get('schema') == CLOSURE_SCHEMA
               and closure.get('finite_admission') == finite_ref
               and closure.get('source_commit') == record['source_commit']
               and closure.get('target_date') == record['target_date']
               and closure.get('execution_date') == record['execution_date']
               and closure.get('publication_verified') is True
               and closure.get('notification_reconciled') is True
               and closure.get('synthetic') is not True,
               'trusted terminal recovery proof differs')
    hashes = closure.get('receipt_hashes')
    ca.require(isinstance(hashes, dict)
               and set(hashes) == {'terminal_runner', 'independent_readback'}
               and all(isinstance(value, str) and re.fullmatch(r'[a-f0-9]{64}', value)
                       for value in hashes.values())
               and closure.get('completion_sha256') == digest(hashes),
               'terminal recovery receipt hash binding differs')
    return closure


def check_owner_continuity(previous, current, room_proof, *, as_of, live):
    ca.require(previous['author_id'] == current['author_id'],
               'transition would change the owner account')
    if previous['room_id'] == current['room_id']:
        ca.require(room_proof is None, 'room proof supplied for an unchanged room')
        return
    required = dict(
        schema='NEW_A_TRUSTED_SAME_ACCOUNT_ROOM_TRANSFER_V1',
        author_id=current['author_id'],
        previous_room_id=previous['room_id'],
        previous_message_id=previous['message_id'],
        previous_text_sha256=previous['text_sha256'],
        room_id=current['room_id'],
        message_id=current['message_id'],
        text_sha256=current['text_sha256'],
        host_verified_same_account=True,
        platform_signature_claimed=False,
    )
    ca.require(isinstance(room_proof, dict)
               and all(room_proof.get(k) == v for k, v in required.items())
               and room_proof.get('synthetic') is not True
               and re.fullmatch(r'[a-f0-9]{64}', str(room_proof.get('host_receipt_sha256', ''))),
               'independent same-account room transfer proof required')
    observed_at = ca.timestamp(room_proof['observed_at'])
    ca.require(ca.timestamp(current['sent_at']) <= observed_at <= as_of
               and (not live or as_of - observed_at <= datetime.timedelta(minutes=15)),
               'room transfer observation is stale or invalid')


def _prepare(repo, plan, *, primary_reader, measurement_reader, raw_reader,
             deployment_reader, decision_reader, authority, closure_reader, room_transfer_reader=None):
    repo = Path(repo).resolve()
    source = ca.head(repo)
    target = ca.target(repo)
    ca.require(plan.get('scope') == ca.SCOPE and plan.get('decision') == DECISION
               and plan.get('strategy') == 'A_BASE' and plan.get('virtual_only') is True
               and plan.get('nonowner_evidence_mode') == 'OWNER_DECISION_UNMEASURED'
               and plan.get('source_commit') == source and plan.get('target') == target
               and 'run_date' not in plan and 'expires_at' not in plan
               and bool(re.fullmatch(r'[a-f0-9]{64}', str(plan.get('expected_activation_sha256', '')))),
               'transition decision, target or activation baseline differs')
    until = ca.timestamp(plan['management_not_after'])
    ca.require(ca.now() < until <= ca.now() + datetime.timedelta(hours=1),
               'transition management authority expired or too broad')
    ca.verify_sources(repo, plan['auth_source_hashes'])
    history = baseline(repo, plan)
    old = history['previous_record']

    owner = ca.primary_message(plan['owner_message'], primary_reader, authority)
    previous_owner = old['owner_message']
    room_proof = None
    if previous_owner['room_id'] != owner['room_id']:
        ca.require(callable(room_transfer_reader), 'independent same-account room transfer reader required')
        room_proof = room_transfer_reader(previous_owner, owner)
    check_owner_continuity(previous_owner, owner, room_proof, as_of=ca.now(), live=True)
    ca.require(callable(closure_reader), 'trusted terminal recovery reader required')
    closure = validate_closure(closure_reader(repo, plan['finite_admission'], history['finite_record']),
                               plan['finite_admission'], history['finite_record'])
    deployment = checked_normal_deployment(source, target, deployment_reader)
    ca.require(callable(decision_reader), 'independent host transition review required')
    review = ca.checked_decision(decision_reader(owner['message_id']), owner, source, target, DECISION)
    expected = dict(previous_acceptance=plan['prior_acceptance'],
                    finite_admission=plan['finite_admission'],
                    expected_activation_sha256=history['activation_sha256'],
                    closure_sha256=digest(closure), management_not_after=plan['management_not_after'],
                    deployment_version_id=deployment['version_id'],
                    historical_auth_source_hashes=old['auth_source_hashes'],
                    current_auth_source_hashes=plan['auth_source_hashes'])
    ca.require(all(review.get(key) == value for key, value in expected.items())
               and review.get('owner_room_transfer') == room_proof
               and review.get('existing_access_policy_preserved') is True,
               'transition review is not bound to the predecessor, closure and current version')
    measurements = release.checked_measurements(plan, measurement_reader, raw_reader, deployment)
    latest = checked_normal_deployment(source, target, deployment_reader)
    ca.require(same_normal_deployment(deployment, latest), 'normal deployment changed during preparation')

    ca.verify_sources(repo, plan['auth_source_hashes'])
    ca.require(ca.head(repo) == source and ca.target(repo) == target and ca.now() < until
               and file_sha(history['activation_path']) == history['activation_sha256']
               and file_sha(history['finite_path']) == plan['finite_admission']['sha256']
               and file_sha(history['original_path']) == history['original_sha256']
               and file_sha(history['old_path']) == plan['prior_acceptance']['sha256'],
               'source, authorization or retained history changed during preparation')
    summary = dict(schema=PREPARATION_SCHEMA, status='prepared-not-applied', source_commit=source,
                   target=target, activation_sha256=history['activation_sha256'],
                   previous_acceptance=plan['prior_acceptance'], finite_admission=plan['finite_admission'],
                   closure_sha256=digest(closure), deployment_version_id=deployment['version_id'],
                   review_sha256=digest(review), measurement_sha256={k: digest(v) for k, v in measurements.items()},
                   checked_at=ca.now().isoformat(), apply_authorized=False)
    return summary, owner, review, closure, latest, measurements


def prepare(repo, plan, *, primary_reader, measurement_reader, raw_reader,
            deployment_reader, decision_reader, authority, closure_reader, room_transfer_reader=None):
    """Prove prerequisite compatibility without issuing or applying anything."""
    summary, *_ = _prepare(repo, plan, primary_reader=primary_reader,
                           measurement_reader=measurement_reader, raw_reader=raw_reader,
                           deployment_reader=deployment_reader, decision_reader=decision_reader,
                           authority=authority, closure_reader=closure_reader,
                           room_transfer_reader=room_transfer_reader)
    return summary


def _review_binding(transition, history, record, completed_at):
    review = ca.checked_decision(transition['host_review'], record['owner_message'],
                                 record['source_commit'], record['target'], DECISION)
    closure = validate_closure(transition['closure'], review['finite_admission'], history['finite_record'])
    deployment = checked_normal_deployment(record['source_commit'], record['target'],
                                            lambda: transition['deployment'])
    old = history['previous_record']
    expected = dict(previous_acceptance=history['historical']['acceptance'],
                    finite_admission=review['finite_admission'],
                    expected_activation_sha256=history['activation_sha256'],
                    closure_sha256=digest(closure),
                    deployment_version_id=deployment['version_id'],
                    historical_auth_source_hashes=old['auth_source_hashes'],
                    current_auth_source_hashes=record['auth_source_hashes'])
    check_owner_continuity(old['owner_message'], record['owner_message'],
                           review.get('owner_room_transfer'), as_of=completed_at, live=False)
    ca.require(all(review.get(key) == value for key, value in expected.items())
               and review.get('existing_access_policy_preserved') is True
               and completed_at <= ca.timestamp(review['management_not_after'])
               and all(value.get('deployment_version_id') == deployment['version_id']
                       for value in record['measurements'].values()),
               'completed transition scope or exact measured Worker differs')


def verify_application(repo, record, grant, current_path, folder, completed, claim):
    """Verify a completed transition while retaining the original recovery audit."""
    audit_path = folder / 'transition.json'
    ca.require(not audit_path.is_symlink()
               and file_sha(audit_path) == completed.get('transition_sha256') == claim.get('transition_sha256'),
               'completed transition audit differs')
    transition = read(audit_path)
    review = transition['host_review']
    archived = folder / 'original.json'
    plan = dict(expected_activation_sha256=grant['expected_activation_sha256'],
                prior_acceptance=completed['previous_acceptance'], finite_admission=review['finite_admission'],
                target=record['target'], source_commit=record['source_commit'])
    history = baseline(repo, plan, archived_activation=archived)
    _review_binding(transition, history, record, ca.timestamp(completed['applied_at']))
    before, current = read(archived), read(current_path)
    expected = {key: value for key, value in before.items() if key != 'operational_admission'}
    expected['owner_acceptance'] = current['owner_acceptance']
    ca.require(current == expected, 'transition changed settings beyond ordinary acceptance')


def _acquire(path, token, held):
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        os.write(descriptor, token.encode())
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    held.append(path)


def apply(repo, plan, issued, *, preflight, primary_reader, measurement_reader,
          raw_reader, deployment_reader, decision_reader, authority, closure_reader, room_transfer_reader=None):
    """Apply one new ordinary grant after an independently reviewed finite closure.

    The caller supplies trusted host readers, including a distinct transition
    decision in addition to the ordinary decision already recorded by issue().
    This function has no command-line or file-supplied trust adapter.
    """
    repo = Path(repo).resolve()
    record = ca.validate_record(repo, issued['acceptance'])
    grant_path, grant = ca.load_reference(repo, issued['application_grant'], 'grants')
    grant_id = grant_path.stem
    ca.require(record['schema'] == ca.SCHEMA
               and grant_id == digest(grant)
               and grant.get('schema') == 'NEW_A_FINITE_ACCEPTANCE_APPLICATION_V1'
               and grant.get('acceptance') == issued['acceptance']
               and grant.get('scope') == ca.SCOPE
               and grant.get('source_commit') == record['source_commit'] == plan['source_commit']
               and grant.get('target') == record['target'] == plan['target']
               and grant.get('owner_message') == record['owner_message']
               and grant.get('expected_activation_sha256') == plan['expected_activation_sha256']
               and grant.get('platform_signature_claimed') is False,
               'ordinary acceptance grant is not bound to this transition')
    activation = private_root(repo) / 'activation.json'
    ca.require(activation.resolve() == activation, 'canonical private activation required')
    folder = ca.root(repo) / 'applications' / grant_id
    ca.require(folder.resolve() == folder, 'transition audit path escapes private root')
    completed_path = folder / 'completed.json'
    if completed_path.exists():
        completed = read(completed_path)
        ca.require(completed.get('schema') == APPLICATION_SCHEMA
                   and completed.get('acceptance') == issued['acceptance']
                   and completed.get('grant') == issued['application_grant'],
                   'grant was already used for another application')
        current_evidence = read(activation)['owner_acceptance']
        ca.require(file_sha(activation) == completed.get('after_sha256')
                   and current_evidence.get('application_id') == grant_id,
                   'completed transition activation changed; reconcile')
        ca.validate_evidence(current_evidence, repo)
        return {**completed, 'same_operation_replay': True}

    def time_remaining():
        current = ca.now()
        grant_start = ca.timestamp(grant['issued_at'])
        grant_end = ca.timestamp(grant['not_after'])
        return (grant_start <= current < grant_end <= grant_start + datetime.timedelta(hours=1)
                and current < ca.timestamp(plan['management_not_after']))

    ca.require(callable(preflight) and time_remaining(), 'transition preflight or valid management grant required')
    configuration = repo / '.cache/weak_early_beta/daily-runner.config.json'
    ca.require(configuration.resolve() == configuration, 'canonical daily config required')
    config_bytes = configuration.read_bytes()
    configured = json.loads(config_bytes.decode('utf-8-sig'))
    runtime = repo / '.cache/weak_early_beta/daily_runtime'
    ca.require((repo / configured['repoPath']).resolve() == repo
               and (repo / configured['runtimeDir']).resolve() == runtime
               and runtime.resolve() == runtime and runtime.is_dir(), 'canonical daily runtime required')
    held = []
    try:
        _acquire(runtime / 'task-entry.lock', grant_id, held)
        ready = preflight()
        ca.require(ready.get('ok') is True and ready.get('sideEffects') is False
                   and ready.get('head') == record['source_commit']
                   and Path(ready.get('repository', '')).resolve() == repo,
                   'formal read-only launch preflight is not ready')
        _acquire(runtime / 'daily.lock', grant_id, held)
        for path in ['.cache/weak_early_beta/exit-reminder-runner.lock', '.cache/weak_early_beta/exit-reminder.lock',
                     'weak_early_beta/state/exit-reminder.lock', 'weak_early_beta/state/daily_runtime/daily.lock']:
            ca.require(not (repo / path).exists(), 'reminder or legacy owner appeared before transition')
        _, owner, review, closure, deployment, measurements = _prepare(
            repo, plan, primary_reader=primary_reader, measurement_reader=measurement_reader,
            raw_reader=raw_reader, deployment_reader=deployment_reader, decision_reader=decision_reader,
            authority=authority, closure_reader=closure_reader, room_transfer_reader=room_transfer_reader)
        ca.require(owner == record['owner_message'] and measurements == record['measurements'],
                   'live transition observations differ from the granted ordinary acceptance')

        original = activation.read_bytes()
        expected_sha = plan['expected_activation_sha256']
        ca.require(hashlib.sha256(original).hexdigest() == expected_sha, 'activation changed before backup')
        evidence = dict(actual_owner_allowed=True, anonymous_denied=True, private_direct_paths_denied=True,
                        existing_auth_unchanged=True, nonowner_denied=False, authenticated_nonowner_observed=False,
                        auth_source_hashes=record['auth_source_hashes'], continuing_acceptance=issued['acceptance'],
                        application_id=grant_id)
        current = json.loads(original.decode('utf-8-sig'))
        value = {key: item for key, item in current.items() if key != 'operational_admission'}
        value['owner_acceptance'] = evidence
        after_sha = hashlib.sha256((encode(value) + os.linesep).encode()).hexdigest()
        transition = dict(host_review=review, closure=closure, deployment=deployment)
        # Creating the application directory exclusively prevents any retry
        # against a partial or ambiguous previous attempt.
        folder.mkdir(parents=True, exist_ok=False)
        transition_ref = ca.immutable(folder / 'transition.json', transition)
        claim = dict(grant=issued['application_grant'], before_sha256=expected_sha, after_sha256=after_sha,
                     transition_sha256=transition_ref['sha256'])
        ca.immutable(folder / 'claim.json', claim)
        with (folder / 'original.json').open('xb') as backup:
            backup.write(original)
            backup.flush()
            os.fsync(backup.fileno())

        candidate = folder / 'candidate.json'
        atomic_write(candidate, value)
        ca.require(candidate.is_file() and file_sha(candidate) == after_sha,
                   'transition candidate readback ambiguous; reconcile')
        applied_at = ca.now().isoformat()
        result = dict(schema=APPLICATION_SCHEMA, **claim, acceptance=issued['acceptance'],
                      previous_acceptance=plan['prior_acceptance'], source_commit=record['source_commit'],
                      applied_at=applied_at, same_operation_replay=False)
        verify_application(repo, record, grant, candidate, folder, result, claim)
        latest_deployment = checked_normal_deployment(record['source_commit'], record['target'], deployment_reader)
        ca.require(same_normal_deployment(deployment, latest_deployment),
                   'normal deployment changed before transition replace')
        ca.require(ca.validate_record(repo, issued['acceptance']) == record
                   and file_sha(activation) == expected_sha and time_remaining()
                   and configuration.read_bytes() == config_bytes,
                   'source, grant, configuration or activation changed before transition replace')
        os.replace(candidate, activation)
        ca.require(file_sha(activation) == after_sha, 'transition activation readback ambiguous; reconcile')
        ca.immutable(completed_path, result)
        ca.validate_evidence(evidence, repo)
        return result
    finally:
        for lock in reversed(held):
            if lock.exists() and lock.read_text() == grant_id:
                lock.unlink()


def ordinary_runtime_release(repo):
    """Read the exact code-only release approved by a completed ordinary transition."""
    from .acceptance import validate_activation

    repo = Path(repo).resolve()
    activation = private_root(repo) / 'activation.json'
    original_sha = file_sha(activation)
    value = read(activation)
    application = value.get('owner_acceptance', {}).get('application_id')
    if value.get('operational_admission') is not None or not application:
        return None
    ca.require(re.fullmatch(r'[a-f0-9]{64}', str(application)), 'invalid ordinary approval application identity')
    folder = ca.root(repo) / 'applications' / application
    ca.require(folder.resolve() == folder, 'ordinary approval application leaves private root')
    completed = read(folder / 'completed.json')
    if completed.get('schema') == 'NEW_A_CONTINUING_ACCEPTANCE_APPLICATION_V1':
        return None
    application_schema = completed.get('schema')
    ca.require(application_schema in {APPLICATION_SCHEMA, ca.MEMBER_ORDINARY_APPLICATION_SCHEMA},
               'unrecognized ordinary approval application')
    validate_activation(value, repo)
    if application_schema == APPLICATION_SCHEMA:
        audit = folder / 'transition.json'
        audit_sha = completed['transition_sha256']
    else:
        audit = folder / 'member-ordinary.json'
        audit_sha = completed['member_ordinary_sha256']
    deployment = read(audit)['deployment']
    source = ca.head(repo)
    target = ca.target(repo)
    checked_normal_deployment(source, target, lambda: deployment)
    ca.require(file_sha(activation) == original_sha == completed['after_sha256']
               and file_sha(audit) == audit_sha,
               'ordinary activation or deployment audit changed during readback')
    return dict(
        schema=RUNTIME_RELEASE_SCHEMA, activation_sha256=original_sha, source_commit=source,
        worker=target['service'], database=target['database_name'],
        **{key: deployment[key]
           for key in ('version_id', 'build_input_sha256', 'policy_sha256', 'ci_run_id', 'tag')},
    )


if __name__ == '__main__':
    if sys.argv[1:] != ['inspect-worker']:
        raise SystemExit('usage: python -m weak_early_beta.new_a.continuing_transition inspect-worker')
    with approval_blobs(Path.cwd()):
        result = ordinary_runtime_release(Path.cwd())
    print(encode(result))
