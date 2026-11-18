"""Fail-closed V2 identity; no provider adapter, credentials or remote operation.

Only legacy exit-reminder receipt additions can advance Git HEAD without a new
acceptance. All tracked blobs remain bound, and each intervening commit is
checked. Fixed-input/loader and actual deployed-artifact evidence are independent
host observations, never inferred from a 200 or from an authentication hash.
"""
import csv
import datetime
import hashlib
import io
import re
import subprocess
from pathlib import Path

from .files import digest

SCHEMA = 'NEW_A_STABLE_EXECUTION_IDENTITY_V1'
RECEIPTS = 'weak_early_beta/state/detections.csv'
MUTABLE = frozenset({'updated_at', 'd6_exit_reminder_discord_url', 'd6_exit_reminded_at'})
DEPENDENCIES = frozenset({'runner_configuration', 'bootstrap_manifest', 'seed',
                          'calendar', 'history_input', 'presentation', 'quotes',
                          'runtime_environment', 'effective_execution',
                          'loader_precedence', 'notification_destination'})
WORKER_MAX_AGE = datetime.timedelta(minutes=5)
HEX = re.compile(r'[a-f0-9]{64}')
COMMIT = re.compile(r'[a-f0-9]{40}')
VERSION = re.compile(r'[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12}')
URL = re.compile(r'https://discord\.com/channels/[1-9][0-9]{16,19}/[1-9][0-9]{16,19}/[1-9][0-9]{16,19}')


def now():
    return datetime.datetime.now(datetime.timezone.utc)


def require(value, reason):
    if not value:
        raise ValueError(reason)


def git(repo, *args):
    return subprocess.check_output(['git', '--no-optional-locks', *args], cwd=repo)


def time(value):
    parsed = datetime.datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(parsed.tzinfo is not None, 'receipt timezone missing')
    return parsed


def parsed_csv(raw):
    require(len(raw) <= 128 * 1024 * 1024, 'receipt CSV exceeds bound')
    rows = list(csv.reader(io.StringIO(raw.decode('utf-8-sig'), newline=''), strict=True))
    require(rows and len(set(rows[0])) == len(rows[0]) and (MUTABLE | {'detection_id'}) <= set(rows[0]),
            'receipt CSV header differs')
    require(all(len(row) == len(rows[0]) for row in rows[1:]), 'receipt CSV row malformed')
    identities = [row[rows[0].index('detection_id')] for row in rows[1:]]
    require(all(identities) and len(set(identities)) == len(identities), 'receipt row identities missing or duplicated')
    return rows


def receipt_transition(before, after):
    """Existing rows only; all non-receipt cells and row order stay exact."""
    left, right = parsed_csv(before), parsed_csv(after)
    require(left[0] == right[0] and len(left) == len(right), 'receipt CSV shape changed')
    columns = {name: left[0].index(name) for name in MUTABLE}
    changed = 0
    for old, new in zip(left[1:], right[1:]):
        if old == new:
            continue
        require(all(a == b for i, (a, b) in enumerate(zip(old, new))
                    if left[0][i] not in MUTABLE), 'non-receipt cell changed')
        # A receipt is append-once. updated_at alone is not an accepted change.
        u, d, at = (columns[k] for k in ['updated_at', 'd6_exit_reminder_discord_url', 'd6_exit_reminded_at'])
        require(old[d] == old[at] == '' and new[d] and new[at] and
                URL.fullmatch(new[d]) is not None, 'receipt replaced, erased or malformed')
        require(new[u] == new[at] and (not old[u] or time(new[u]) >= time(old[u])),
                'receipt timestamp changed outside delivery')
        observed = time(new[at])
        require(observed <= now(), 'receipt timestamp is in future')
        if 'sixth_xtks_exit_date' in left[0]:
            require(observed.astimezone(datetime.timezone(datetime.timedelta(hours=9))).date().isoformat()
                    == old[left[0].index('sixth_xtks_exit_date')], 'receipt outside recorded D6 date')
        changed += 1
    require(changed > 0, 'receipt commit has no append-only receipt')
    return changed


def tracked_identity(repo, source):
    require(COMMIT.fullmatch(source) is not None, 'full source commit required')
    entries = []
    for line in git(repo, 'ls-tree', '-rz', '--full-tree', source).split(b'\0'):
        if not line:
            continue
        metadata, name = line.split(b'\t', 1)
        mode, kind, object_id = metadata.decode('ascii').split()
        path = name.decode('utf-8')
        require(kind == 'blob' and mode in {'100644', '100755'},
                'symlink or submodule identity unsupported')
        # Git's blob identity pins every tracked path, including build inputs,
        # configuration and ordinary CSV data. No directory/extension exclusion.
        entries.append([mode, path, object_id])
    require(any(item[1] == RECEIPTS for item in entries), 'receipt baseline absent')
    return {'schema': SCHEMA, 'tracked_tree_sha256': digest(entries),
            'receipt_blob_sha256': hashlib.sha256(git(repo, 'show', source + ':' + RECEIPTS)).hexdigest()}


def verify_receipt_descendant(repo, anchor, current):
    require(COMMIT.fullmatch(anchor) is not None and COMMIT.fullmatch(current) is not None,
            'full lineage commits required')
    # Fail on dirty/untracked executable files, not merely on a tracked diff.
    require(git(repo, 'status', '--porcelain', '--untracked-files=normal') == b'',
            'execution checkout is not clean')
    require(git(repo, 'rev-parse', 'HEAD').decode().strip() == current, 'execution HEAD changed')
    if anchor == current:
        return []
    subprocess.run(['git', '--no-optional-locks', 'merge-base', '--is-ancestor', anchor, current],
                   cwd=repo, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    lineage = git(repo, 'rev-list', '--reverse', anchor + '..' + current).decode().splitlines()
    require(len(lineage) <= 4096, 'receipt lineage exceeds bound')
    previous, audit = anchor, []
    for source in lineage:
        parents = git(repo, 'rev-list', '--parents', '-n', '1', source).decode().split()
        require(parents == [source, previous], 'receipt lineage merge or discontinuity')
        paths = git(repo, 'diff-tree', '--no-commit-id', '--name-only', '-r', '-z', previous, source).split(b'\0')
        require(paths == [RECEIPTS.encode(), b''], 'non-receipt tracked change requires new acceptance')
        # File modes matter even when cells happen to compare equal.
        for commit in [previous, source]:
            require(git(repo, 'ls-tree', commit, '--', RECEIPTS).startswith(b'100644 blob '),
                    'receipt path mode changed')
        count = receipt_transition(git(repo, 'show', previous + ':' + RECEIPTS),
                                   git(repo, 'show', source + ':' + RECEIPTS))
        audit.append({'commit': source, 'rows': count})
        previous = source
    require(previous == current, 'receipt lineage incomplete')
    return audit


def checked_dependencies(source, target, reader):
    """Safe metadata from the existing loader, not reads of secret files.

    The existing loader must attest its effective nonsecret command/settings,
    selected references/precedence, DB target and existing notification identity,
    not merely the bytes or path of an unused configuration file. No such
    production adapter is implemented by this module.
    Fixed bootstrap inputs/runner config/environment are pinned. Daily mutable
    state, newly acquired prices, operational claims and output DBs MUST NOT be
    included: their existing per-run quality/watermark guards still own them.
    """
    require(callable(reader), 'trusted existing-loader identity reader unavailable')
    value = reader()
    require(isinstance(value, dict) and value.get('schema') == 'NEW_A_HOST_FIXED_DEPENDENCIES_V1'
            and value.get('source_commit') == source and value.get('target') == target
            and value.get('synthetic') is not True and value.get('secret_files_read') is False
            and value.get('existing_loader_verified') is True
            and value.get('per_run_input_guards_unchanged') is True,
            'fixed dependency provenance unavailable')
    pins = value.get('hashes', {})
    require(set(pins) == DEPENDENCIES and all(isinstance(h, str) and HEX.fullmatch(h) for h in pins.values()),
            'fixed dependency identities incomplete')
    return dict(schema=value['schema'], target=target, hashes=pins)


def checked_worker(source, target, reader):
    require(callable(reader), 'trusted actual Worker identity reader unavailable')
    value = reader()
    require(isinstance(value, dict) and value.get('schema') == 'NEW_A_HOST_ACTUAL_WORKER_IDENTITY_V1'
            and value.get('runtime_source_commit') == source and value.get('target') == target
            and COMMIT.fullmatch(str(value.get('deployed_source_commit', '')))
            and value.get('synthetic') is not True and value.get('platform_signature_claimed') is False
            and value.get('actual_responding_version_verified') is True
            and value.get('artifact_source_verified') is True
            and value.get('normal_authorization_preserved') is True
            and value.get('routing_kind') == 'NORMAL_PRODUCTION_URL_NO_OVERRIDE'
            and VERSION.fullmatch(str(value.get('deployment_id', '')))
            and value.get('deployment_versions') == [dict(version_id=value.get('version_id'), percentage=100)]
            and VERSION.fullmatch(str(value.get('version_id', '')))
            and HEX.fullmatch(str(value.get('artifact_sha256', '')))
            and HEX.fullmatch(str(value.get('raw_receipt_sha256', ''))),
            'actual responding Worker or artifact not proven')
    require(now() - WORKER_MAX_AGE <= time(value['observed_at']) <= now(),
            'Worker observation stale or in future')
    require(time(value['deployed_at']) <= time(value['observed_at']), 'Worker observation predates deployment')
    return {k: value[k] for k in ['schema', 'target', 'deployed_source_commit', 'deployment_id',
                                 'deployment_versions', 'deployed_at', 'routing_kind', 'version_id', 'artifact_sha256']}, value


def bind(repo, source, target, *, dependency_reader, worker_reader):
    verify_receipt_descendant(repo, source, source)
    dependencies = checked_dependencies(source, target, dependency_reader)
    worker, observation = checked_worker(source, target, worker_reader)
    require(worker['deployed_source_commit'] == source, 'new V2 requires a genuine exact-source deployment')
    binding = dict(schema=SCHEMA, anchor_source=source, tracked=tracked_identity(repo, source),
                   dependencies=dependencies, worker=worker)
    # A callback cannot replace HEAD/config while returning a prior observation.
    verify(repo, binding, source, target, dependency_reader=dependency_reader, worker_reader=worker_reader)
    return binding, observation


def verify(repo, binding, current, target, *, dependency_reader, worker_reader):
    require(binding.get('schema') == SCHEMA, 'stable identity contract required')
    anchor = binding['anchor_source']
    require(binding.get('tracked') == tracked_identity(repo, anchor), 'accepted anchor tree changed')
    audit = verify_receipt_descendant(repo, anchor, current)
    # Host metadata is about the CURRENT loader/response, not the old certificate.
    require(checked_dependencies(current, target, dependency_reader) == binding['dependencies'],
            'fixed configuration, bootstrap input or runtime changed')
    worker, _ = checked_worker(current, target, worker_reader)
    require(worker == binding['worker'], 'actual Worker version or deployed artifact changed')
    require(checked_dependencies(current, target, dependency_reader) == binding['dependencies'],
            'fixed dependencies changed during observation')
    latest, _ = checked_worker(current, target, worker_reader)
    require(latest == worker, 'Worker changed during observation')
    require(verify_receipt_descendant(repo, anchor, current) == audit,
            'execution changed during observation')
    return audit


def verify_measurements(measurements, observation, raw_reader):
    require(callable(raw_reader), 'independent normal-response raw reader unavailable')
    for kind, measurement in measurements.items():
        raw = raw_reader(kind)
        require(isinstance(raw, dict) and raw.get('synthetic') is not True and
                raw.get('source_commit') == observation['runtime_source_commit'] and
                raw.get('target') == observation['target'] and
                raw.get('version_id') == observation['version_id'] and
                raw.get('artifact_sha256') == observation['artifact_sha256'] and
                raw.get('receipt_sha256') == measurement['raw_receipt_sha256'] and
                raw.get('observed_at') == measurement['observed_at'] and
                now() - datetime.timedelta(hours=1) <= time(raw['observed_at']) <= now() and
                time(observation['deployed_at']) <= time(raw['observed_at']) and
                measurement.get('deployment_version_id') == observation['version_id'],
                'same-version raw measurement unavailable')
        if kind == 'owner':
            require(raw.get('owner_identity_verified') is True and
                    raw.get('source_kind') == 'EXISTING_LEGITIMATE_OWNER_SESSION' and
                    raw.get('document') == dict(path='/weak_early_beta_latest.html', status=200) and
                    raw.get('api') == dict(path='/api/cloud/new-a-finite/access', status=200,
                                          body=dict(authorized=True, strategy='A_BASE')),
                    'owner normal-response proof unavailable')
