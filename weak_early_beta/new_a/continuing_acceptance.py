"""Continuing operator acceptance, distinct from finite administration/recovery.

The host must supply actual primary-message and measurement readers and verified
owner identity. These local operator records are not platform signatures. No
browser authorization, provider permission, schedule or credential is changed.
"""
import datetime
import hashlib
import os
import uuid
import re
from pathlib import Path
import subprocess
from .files import atomic_write, digest, encode, file_sha, private_root, read

SCHEMA = 'NEW_A_CONTINUING_OWNER_ACCEPTANCE_V1'
STABLE_SCHEMA = 'NEW_A_CONTINUING_OWNER_ACCEPTANCE_V2'
STABLE_DECISION = 'CONTINUE_UNTIL_REVOKED_OR_BOUND_EXECUTION_CHANGED'
STABLE_REVIEW = 'CONTINUING_DAILY_WITH_STABLE_EXECUTION_IDENTITY_NONOWNER_UNMEASURED'
TRANSITION_APPLICATION_SCHEMA = 'NEW_A_CONTINUING_TRANSITION_APPLICATION_V1'
MEMBER_ORDINARY_APPLICATION_SCHEMA = 'NEW_A_MEMBER_ORDINARY_APPLICATION_V1'
# A member application adds two recursive frames per historical link. Keep
# the local verifier comfortably below Python's default stack limit while
# revalidating every retained acceptance and revocation through the root.
MAX_ACCEPTANCE_AUDIT_DEPTH = 128
SCOPE = 'EXISTING_NEW_A_PERSONAL_PC_DAILY_V1'
SERVICE = 'tentei-kyokuchi-cloud'
AUTH_FILES = frozenset(['report-gate/src/index.ts', *[
    'weak-early-beta-gate/src/' + name + '.ts' for name in
    ['index', 'cloud-owner-only', 'cloud-role-authority', 'cloud-membership', 'cloud-api', 'new-a-cloud']]])
PATHS = {
    'owner': {'/weak_early_beta_latest.html', '/api/cloud/new-a-finite/access'},
    'anonymous': {'/weak_early_beta_latest.html', '/weak_early_beta_analytics.html', '/api/cloud/new-a-finite/access', '/auth/check'},
    'direct': {'/api/cloud/new-a-finite/input/manifest.json', '/api/cloud/new-a-finite/preferences', '/new-a-assets/new-a-finite-worker.generated.js'},
}

def now():
    return datetime.datetime.now(datetime.timezone.utc)

def head(repo):
    return subprocess.check_output(['git', '--no-optional-locks', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()

def require(condition, reason):
    if not condition:
        raise ValueError(reason)

def root(repo):
    repo = Path(repo).resolve()
    value = private_root(repo) / 'continuing-acceptance'
    require(value.resolve().is_relative_to(repo), 'private acceptance root escapes repository')
    return value

def target(repo):
    config = read(Path(repo) / 'weak-early-beta-gate/wrangler.jsonc')
    databases = [d for d in config.get('d1_databases', []) if d.get('binding') == 'CLOUD_DB']
    require(config.get('name') == SERVICE and len(databases) == 1, 'unexpected service or D1 binding')
    database = databases[0]
    require(database.get('database_name') == 'tentei-cloud-settings' and isinstance(database.get('database_id'), str) and database['database_id'], 'unexpected database target')
    return dict(service=SERVICE, binding='CLOUD_DB', database_name=database['database_name'], database_id=database['database_id'])

def verify_sources(repo, pins):
    repo = Path(repo).resolve()
    require(set(pins) == AUTH_FILES, 'authentication source set changed')
    for name, pin in pins.items():
        path = (repo / name).resolve()
        require(path.is_relative_to(repo) and file_sha(path) == pin, 'authentication source changed')

def timestamp(value):
    result = datetime.datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(result.tzinfo is not None, 'timezone required')
    return result

def primary_message(binding, reader, authority):
    require(callable(reader), 'independent host primary reader required')
    require(all(isinstance(binding.get(k), str) and binding[k] for k in ['message_id', 'author_id', 'room_id', 'text_sha256']), 'primary binding incomplete')
    require(binding['author_id'] == authority.get('author_id') and binding['room_id'] == authority.get('room_id'), 'not the host-verified owner authority')
    result = reader(binding['message_id'])
    message = result.get('message', {})
    require(result.get('partial') is False and result.get('room_id') == authority['room_id'] and message.get('author') == 'user' and message.get('author_id') == authority['author_id'] and message.get('channel') == 'chatgpt' and message.get('message_id') == binding['message_id'] and message.get('deleted_at') is None and digest(message.get('content', {}).get('text')) == binding['text_sha256'], 'actual owner primary message mismatch')
    require(timestamp(message['sent_at']) <= now(), 'owner primary timestamp invalid')
    return {**binding, 'sent_at': message['sent_at']}

def checked_decision(review, owner, source, destination, decision):
    # Explicit operator interpretation of the actual primary read, not a claim
    # that the platform supplied a signed/structured authorization object.
    require(review.get('schema') == 'NEW_A_HOST_OPERATOR_INTERPRETATION_V1' and review.get('decision') == decision and review.get('scope') == SCOPE and review.get('source_commit') == source and review.get('target') == destination and review.get('message_id') == owner['message_id'] and review.get('text_sha256') == owner['text_sha256'] and review.get('author_id') == owner['author_id'] and review.get('room_id') == owner['room_id'] and review.get('platform_signature_claimed') is False, 'host-reviewed owner intent or scope mismatch')
    return review

def verify_measurement(record, kind, source, pins, destination):
    require(record.get('schema') == 'NEW_A_HOST_OBSERVED_MEASUREMENT_V1' and record.get('kind') == kind and record.get('source_commit') == source and record.get('auth_source_hashes') == pins and record.get('target') == destination and record.get('platform_signature_claimed') is False and record.get('synthetic') is not True, 'measurement provenance or version mismatch')
    require(timestamp(record['observed_at']) <= now() and isinstance(record.get('raw_receipt_sha256'), str) and re.fullmatch('[a-f0-9]{64}', record['raw_receipt_sha256']), 'measurement observation not established')
    require(record.get('authenticated_nonowner_observed') is False, 'unmeasured nonowner must remain false')
    rows = record.get('observations', [])
    require(isinstance(rows, list) and len({r.get('path') for r in rows}) == len(rows), 'measurement routes missing or duplicated')
    by_path = {r.get('path'): r for r in rows}
    require(PATHS[kind].issubset(by_path), 'required measured routes absent')
    if kind == 'owner':
        require(record.get('source_kind') == 'EXISTING_LEGITIMATE_OWNER_SESSION' and record.get('owner_identity_verified') is True, 'legitimate owner observation required')
        require(all(by_path[p].get('status') == 200 for p in PATHS[kind]), 'owner document or API was not allowed')
    else:
        require(record.get('source_kind') == 'NO_AUTH_NO_COOKIES' and record.get('cookies_sent') is False and record.get('authorization_sent') is False, 'fresh anonymous observation required')
        require(all(by_path[p].get('status') in [302, 303, 307, 401, 403] and by_path[p].get('private_gate') is True for p in PATHS[kind]), 'document or direct route not denied')

def immutable(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (encode(value) + '\n').encode('utf8')
    with path.open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return {'path': str(path), 'sha256': hashlib.sha256(raw).hexdigest()}

def reference(repo, path):
    return {'path': str(path.relative_to(Path(repo).resolve())), 'sha256': file_sha(path)}

def load_reference(repo, ref, section):
    path = (Path(repo).resolve() / ref.get('path', '')).resolve()
    section_root = (root(repo) / section).resolve()
    require(path.is_relative_to(section_root) and path.suffix == '.json' and file_sha(path) == ref.get('sha256'), 'private operator reference mismatch')
    return path, read(path)

def issue(repo, plan, *, primary_reader, measurement_reader, decision_reader, authority,
          dependency_reader=None, worker_reader=None, raw_reader=None):
    """Host-reviewed intent is required; no generic approval-file CLI is installed."""
    repo = Path(repo).resolve()
    stable = plan.get('acceptance_schema') == STABLE_SCHEMA
    require(plan.get('acceptance_schema', SCHEMA) in {SCHEMA, STABLE_SCHEMA}, 'unsupported acceptance schema')
    require(stable or 'execution_identity' not in plan, 'old acceptance cannot acquire a stable identity')
    require(plan.get('scope') == SCOPE and plan.get('decision') == (STABLE_DECISION if stable else 'CONTINUE_UNTIL_REVOKED_OR_BOUND_SOURCE_CHANGED') and plan.get('strategy') == 'A_BASE' and plan.get('virtual_only') is True and plan.get('nonowner_evidence_mode') == 'OWNER_DECISION_UNMEASURED', 'continuing decision scope not approved')
    require(plan.get('source_commit') == head(repo) and plan.get('target') == target(repo), 'continuing target or source mismatch')
    require('run_date' not in plan and 'expires_at' not in plan, 'dated recovery cannot become continuing acceptance')
    until = timestamp(plan['management_not_after'])
    require(now() < until <= now() + datetime.timedelta(hours=1), 'management authority expired or too broad')
    require(isinstance(plan.get('expected_activation_sha256'), str) and re.fullmatch('[a-f0-9]{64}', plan['expected_activation_sha256']), 'activation baseline required')
    verify_sources(repo, plan['auth_source_hashes'])
    owner = primary_message(plan['owner_message'], primary_reader, authority)
    require(callable(decision_reader), 'host operator intent review required')
    review = checked_decision(decision_reader(owner['message_id']), owner, plan['source_commit'], plan['target'], STABLE_REVIEW if stable else 'CONTINUING_DAILY_WITH_NONOWNER_UNMEASURED')
    require(callable(measurement_reader) and set(plan['measurements']) == set(PATHS), 'independent measured acceptance required')
    measurements = {}
    for kind, binding in plan['measurements'].items():
        observed = measurement_reader(binding['id'])
        require(digest(observed) == binding.get('sha256'), 'actual host measurement changed')
        verify_measurement(observed, kind, plan['source_commit'], plan['auth_source_hashes'], plan['target'])
        measurements[kind] = observed
    identity = None
    if stable:
        from . import execution_identity as execution
        identity, observed = execution.bind(repo, plan['source_commit'], plan['target'],
                                           dependency_reader=dependency_reader, worker_reader=worker_reader)
        require(plan.get('execution_identity') == identity, 'reviewed execution identity changed')
        require(review.get('acceptance_schema') == STABLE_SCHEMA and
                review.get('execution_identity_sha256') == digest(identity),
                'owner review not bound to V2 execution identity')
        execution.verify_measurements(measurements, observed, raw_reader)
    record = dict(schema=STABLE_SCHEMA if stable else SCHEMA, scope=SCOPE, strategy='A_BASE', virtual_only=True, target=plan['target'], source_commit=plan['source_commit'], auth_source_hashes=plan['auth_source_hashes'], decision=plan['decision'], owner_message=owner, host_decision=review, measurements=measurements, nonowner_denied=False, authenticated_nonowner_observed=False, issued_at=now().isoformat(), issuance='HOST_VERIFIED_OPERATOR_ATTESTATION_V1', platform_signature_claimed=False)
    if stable: record['execution_identity'] = identity
    record['record_sha256'] = digest(record)
    path = root(repo) / 'records' / (record['record_sha256'] + '.json')
    if path.exists():
        require(path.read_bytes() == (encode(record) + '\n').encode(), 'immutable acceptance conflict')
    else:
        immutable(path, record)
    ref = reference(repo, path)
    # Finite authority to apply once; its expiry never becomes the runtime lifetime.
    grant = dict(schema='NEW_A_FINITE_ACCEPTANCE_APPLICATION_V1', acceptance=ref, scope=SCOPE, source_commit=record['source_commit'], target=record['target'], expected_activation_sha256=plan['expected_activation_sha256'], issued_at=now().isoformat(), not_after=until.isoformat(), nonce=uuid.uuid4().hex, owner_message=owner, platform_signature_claimed=False)
    grant_path = root(repo) / 'grants' / (digest(grant) + '.json')
    immutable(grant_path, grant)
    return {'acceptance': ref, 'application_grant': reference(repo, grant_path)}

def _verify_historical_auth_sources(repo, source, pins):
    # Match the original raw pin to a Git blob or its Windows checkout bytes.
    # An old pin is never converted or replaced by a normalized checksum.
    require(re.fullmatch(r'[a-f0-9]{40}', str(source)) and set(pins) == AUTH_FILES,
            'historical authentication source identity differs')
    for name, pin in pins.items():
        blob = subprocess.check_output(['git', '--no-optional-locks', 'show', f'{source}:{name}'], cwd=repo)
        windows_checkout = blob.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')
        require(any(hashlib.sha256(raw).hexdigest() == pin for raw in (blob, windows_checkout)),
                'historical authentication source bytes cannot reproduce the exact pin')


def validate_record(repo, ref, *, _historical_source=None, _historical_git_sources=False,
                    dependency_reader=None, worker_reader=None):
    path, value = load_reference(repo, ref, 'records')
    record = dict(value)
    pin = record.pop('record_sha256', None)
    require(digest(record) == pin and path.stem == pin and record.get('schema') in {SCHEMA, STABLE_SCHEMA} and record.get('scope') == SCOPE and record.get('strategy') == 'A_BASE' and record.get('virtual_only') is True and record.get('decision') == (STABLE_DECISION if record.get('schema') == STABLE_SCHEMA else 'CONTINUE_UNTIL_REVOKED_OR_BOUND_SOURCE_CHANGED') and record.get('issuance') == 'HOST_VERIFIED_OPERATOR_ATTESTATION_V1' and record.get('platform_signature_claimed') is False, 'continuing acceptance contract mismatch')
    require('expires_at' not in record and 'run_date' not in record and record.get('nonowner_denied') is False and record.get('authenticated_nonowner_observed') is False, 'continuing evidence falsely dated or measured')
    require(record.get('target') == target(repo), 'accepted source or target changed')
    if record['schema'] == SCHEMA:
        require('execution_identity' not in record and record.get('source_commit') == (_historical_source or head(repo)), 'accepted source or target changed')
    else:
        from . import execution_identity as execution
        binding = record.get('execution_identity', {})
        require(binding.get('anchor_source') == record.get('source_commit'), 'stable anchor source differs')
        if _historical_source is not None:
            require(record['source_commit'] == _historical_source and binding.get('tracked') == execution.tracked_identity(repo, _historical_source), 'historical stable identity differs')
        else:
            execution.verify(repo, binding, head(repo), record['target'], dependency_reader=dependency_reader, worker_reader=worker_reader)
    checked_decision(record['host_decision'], record['owner_message'], record['source_commit'], record['target'], STABLE_REVIEW if record['schema'] == STABLE_SCHEMA else 'CONTINUING_DAILY_WITH_NONOWNER_UNMEASURED')
    if record['schema'] == STABLE_SCHEMA:
        require(record['host_decision'].get('acceptance_schema') == STABLE_SCHEMA and
                record['host_decision'].get('execution_identity_sha256') == digest(record['execution_identity']),
                'owner review not bound to V2 execution identity')
    require(not (root(repo) / 'revocations' / (pin + '.json')).exists(), 'continuing acceptance revoked')
    if _historical_git_sources:
        require(_historical_source is not None and record['schema'] == SCHEMA,
                'explicit historical V1 source required')
        _verify_historical_auth_sources(repo, _historical_source, record['auth_source_hashes'])
    else:
        verify_sources(repo, record['auth_source_hashes'])
    require(set(record['measurements']) == set(PATHS), 'measured acceptance incomplete')
    for kind, measurement in record['measurements'].items():
        verify_measurement(measurement, kind, record['source_commit'], record['auth_source_hashes'], record['target'])
    return record

def validate_evidence(evidence, repo, *, _activation_path=None, _historical_source=None, _seen=None,
                      _historical_git_sources=False,
                      dependency_reader=None, worker_reader=None):
    require(all(evidence.get(k) is True for k in ['actual_owner_allowed', 'anonymous_denied', 'private_direct_paths_denied', 'existing_auth_unchanged']), 'other owner acceptance incomplete')
    require(evidence.get('nonowner_denied') is False and evidence.get('authenticated_nonowner_observed') is False, 'unmeasured nonowner must remain false')
    _seen=set() if _seen is None else set(_seen)
    acceptance_sha = evidence['continuing_acceptance']['sha256']
    require(acceptance_sha not in _seen, 'acceptance audit chain cycle')
    require(len(_seen) < MAX_ACCEPTANCE_AUDIT_DEPTH, 'acceptance audit chain depth limit exceeded')
    _seen.add(acceptance_sha)
    record = validate_record(repo, evidence['continuing_acceptance'], _historical_source=_historical_source,
                             _historical_git_sources=_historical_git_sources,
                             dependency_reader=dependency_reader, worker_reader=worker_reader)
    require(evidence.get('auth_source_hashes') == record['auth_source_hashes'], 'accepted source pins differ')
    application_id = evidence.get('application_id')
    require(isinstance(application_id, str) and re.fullmatch('[a-f0-9]{64}', application_id), 'completed application audit required')
    folder = (root(repo) / 'applications' / application_id).resolve()
    require(folder.is_relative_to(root(repo).resolve()) and (folder / 'completed.json').is_file(), 'completed application audit missing')
    completed = read(folder / 'completed.json')
    claim = read(folder / 'claim.json')
    grant_path, grant = load_reference(repo, completed['grant'], 'grants')
    transition = completed.get('schema') == TRANSITION_APPLICATION_SCHEMA
    member_upgrade = completed.get('schema') == MEMBER_ORDINARY_APPLICATION_SCHEMA
    activation_path = _activation_path or (private_root(repo) / 'activation.json')
    require(grant_path.stem == application_id == digest(grant) and (transition or member_upgrade or completed.get('schema') == 'NEW_A_CONTINUING_ACCEPTANCE_APPLICATION_V1') and completed.get('acceptance') == evidence['continuing_acceptance'] and grant.get('acceptance') == evidence['continuing_acceptance'] and completed.get('source_commit') == record['source_commit'] and claim.get('grant') == completed['grant'] and claim.get('before_sha256') == completed.get('before_sha256') == file_sha(folder / 'original.json') and claim.get('after_sha256') == completed.get('after_sha256') == file_sha(activation_path), 'completed application audit or activation changed')
    require(grant.get('schema') == 'NEW_A_FINITE_ACCEPTANCE_APPLICATION_V1' and grant.get('scope') == SCOPE and grant.get('source_commit') == record['source_commit'] and grant.get('target') == record['target'] and grant.get('owner_message') == record['owner_message'] and grant.get('platform_signature_claimed') is False and grant.get('expected_activation_sha256') == completed['before_sha256'] and timestamp(grant['issued_at']) <= timestamp(completed['applied_at']) <= timestamp(grant['not_after']) <= timestamp(grant['issued_at']) + datetime.timedelta(hours=1), 'application was not completed within its finite authority')
    original_activation=read(folder/'original.json')
    require((original_activation.get('active') is True)==bool(completed.get('previous_acceptance')), 'active predecessor audit link missing or invented')
    if transition:
        from . import continuing_transition
        continuing_transition.verify_application(repo, record, grant, activation_path, folder, completed, claim)
    elif member_upgrade:
        from . import member_ordinary_acceptance
        member_ordinary_acceptance.verify_application(repo, record, grant, activation_path, folder, completed, claim, _seen)
    elif completed.get('previous_acceptance'):
        previous=read(folder/'original.json')
        require(previous.get('active') is True and previous.get('external_actions_approved') is True and previous.get('owner_acceptance',{}).get('continuing_acceptance')==completed['previous_acceptance'], 'upgraded original activation differs')
        _,old=load_reference(repo,completed['previous_acceptance'],'records')
        require(old['source_commit']!=record['source_commit'] and old['target']==record['target'] and old['auth_source_hashes']==record['auth_source_hashes'] and all(old['owner_message'][k]==record['owner_message'][k] for k in ['author_id','room_id']), 'upgrade broadened owner, target or authentication source')
        validate_evidence(previous['owner_acceptance'],repo,_activation_path=folder/'original.json',_historical_source=old['source_commit'],_seen=_seen)
    return record

def revoke(repo, ref, binding, *, primary_reader, decision_reader, authority):
    # Revocation remains possible after a code change; it only closes permission.
    path, value = load_reference(repo, ref, 'records')
    require(value.get('owner_message', {}).get('author_id') == authority.get('author_id') and value.get('owner_message', {}).get('room_id') == authority.get('room_id'), 'only original owner authority may revoke')
    owner = primary_message(binding, primary_reader, authority)
    require(callable(decision_reader), 'host operator revocation review required')
    review = checked_decision(decision_reader(owner['message_id']), owner, value['source_commit'], value['target'], 'REVOKE_CONTINUING_ACCEPTANCE')
    event = dict(schema='NEW_A_CONTINUING_ACCEPTANCE_REVOKED_V1', acceptance=ref, owner_message=owner, host_decision=review, revoked_at=now().isoformat(), platform_signature_claimed=False)
    immutable(root(repo) / 'revocations' / (path.stem + '.json'), event)
    return event

def apply(repo, issued, *, preflight, previous_acceptance=None, arbitration_owner=None,
          dependency_reader=None, worker_reader=None):
    """Only the original finite grant can CAS-apply this accepted record once."""
    repo = Path(repo).resolve()
    record = validate_record(repo, issued['acceptance'], dependency_reader=dependency_reader, worker_reader=worker_reader)
    grant_path, grant = load_reference(repo, issued['application_grant'], 'grants')
    require(grant_path.stem == digest(grant) and grant.get('schema') == 'NEW_A_FINITE_ACCEPTANCE_APPLICATION_V1' and grant.get('acceptance') == issued['acceptance'] and grant.get('scope') == SCOPE and grant.get('source_commit') == record['source_commit'] and grant.get('target') == record['target'] and grant.get('owner_message') == record['owner_message'] and grant.get('platform_signature_claimed') is False and timestamp(grant['issued_at']) <= now() < timestamp(grant['not_after']) <= timestamp(grant['issued_at']) + datetime.timedelta(hours=1), 'finite application grant expired or mismatched')
    require(callable(preflight), 'normal launch preflight required')
    activation = private_root(repo) / 'activation.json'
    require(read(activation).get('operational_admission') is None, 'finite recovery requires the formal continuing transition')
    operation = root(repo) / 'applications' / grant_path.stem
    operation.mkdir(parents=True, exist_ok=True)
    completed = operation / 'completed.json'
    if completed.exists():
        result = read(completed)
        require(result.get('after_sha256') == file_sha(activation), 'completed activation changed; reconcile')
        validate_evidence(read(activation)['owner_acceptance'], repo, dependency_reader=dependency_reader, worker_reader=worker_reader)
        return {**result, 'same_operation_replay': True}
    runtime = repo / '.cache/weak_early_beta/daily_runtime'
    runtime.mkdir(parents=True, exist_ok=True)
    held = []
    def claim_lock(path):
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        try:
            os.write(fd, grant_path.stem.encode()); os.fsync(fd)
        finally:
            os.close(fd)
        held.append(path)
    try:
        if arbitration_owner is None:claim_lock(runtime / 'task-entry.lock')
        else:require(isinstance(arbitration_owner,str) and (runtime/'task-entry.lock').read_text()==arbitration_owner, 'existing formal launch arbitration differs')
        ready = preflight()
        require(ready.get('ok') is True and ready.get('head') == record['source_commit'] and Path(ready.get('repository', '')).resolve() == repo, 'normal launch preflight not ready')
        claim_lock(runtime / 'daily.lock')
        for name in ['.cache/weak_early_beta/exit-reminder-runner.lock', '.cache/weak_early_beta/exit-reminder.lock', 'weak_early_beta/state/exit-reminder.lock', 'weak_early_beta/state/daily_runtime/daily.lock']:
            require(not (repo / name).exists(), 'reminder or legacy lock exists')
        require(file_sha(activation) == grant['expected_activation_sha256'], 'activation baseline changed')
        current = read(activation)
        require(current.get('schema') == 'NEW_A_OWNER_ACTIVATION_V1' and current.get('strategy') == 'A_BASE', 'activation contract differs')
        require(current.get('operational_admission') is None, 'finite recovery requires the formal continuing transition')
        if previous_acceptance is None:
            require(current.get('active') is False and current.get('external_actions_approved') is False, 'inactive exact baseline required')
        else:
            require(current.get('active') is True and current.get('external_actions_approved') is True and current.get('owner_acceptance',{}).get('continuing_acceptance')==previous_acceptance, 'active source upgrade baseline differs')
            _,old=load_reference(repo,previous_acceptance,'records')
            validate_evidence(current['owner_acceptance'], repo, _historical_source=old['source_commit'],
                              _seen={issued['acceptance']['sha256']})
            require(old['source_commit']!=record['source_commit'] and old['target']==record['target'] and old['auth_source_hashes']==record['auth_source_hashes'] and all(old['owner_message'][k]==record['owner_message'][k] for k in ['author_id','room_id']), 'source upgrade broadens continuing acceptance')
        evidence = dict(actual_owner_allowed=True, anonymous_denied=True, private_direct_paths_denied=True, existing_auth_unchanged=True, nonowner_denied=False, authenticated_nonowner_observed=False, auth_source_hashes=record['auth_source_hashes'], continuing_acceptance=issued['acceptance'], application_id=grant_path.stem)
        value = {**current, 'active': True, 'external_actions_approved': True, 'owner_acceptance': evidence}
        after_sha = hashlib.sha256((encode(value) + os.linesep).encode()).hexdigest()
        immutable(operation / 'claim.json', dict(grant=issued['application_grant'], before_sha256=grant['expected_activation_sha256'], after_sha256=after_sha))
        raw = activation.read_bytes()
        require(hashlib.sha256(raw).hexdigest() == grant['expected_activation_sha256'], 'activation changed before backup')
        with (operation / 'original.json').open('xb') as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        require(file_sha(activation) == grant['expected_activation_sha256'] and head(repo) == record['source_commit'], 'activation or source changed before replace')
        validate_record(repo, issued['acceptance'], dependency_reader=dependency_reader, worker_reader=worker_reader)
        require(now() < timestamp(grant['not_after']), 'finite application authority expired before replace')
        atomic_write(activation, value)
        require(file_sha(activation) == after_sha, 'activation readback ambiguous; reconcile')
        result = dict(schema='NEW_A_CONTINUING_ACCEPTANCE_APPLICATION_V1', before_sha256=grant['expected_activation_sha256'], after_sha256=after_sha, acceptance=issued['acceptance'], grant=issued['application_grant'], source_commit=record['source_commit'], applied_at=now().isoformat(), same_operation_replay=False)
        if previous_acceptance is not None:result['previous_acceptance']=previous_acceptance
        atomic_write(completed, result)
        validate_evidence(evidence, repo, dependency_reader=dependency_reader, worker_reader=worker_reader)
        return result
    finally:
        for path in reversed(held):
            if path.exists() and path.read_text() == grant_path.stem:
                path.unlink()
