"""Prepare an accepted candidate without advancing the operating checkout.

No deployment, Git update, launch, credential loading or production adapter is
installed here. Independent host readers remain mandatory. A prepared directory
is not authority to change traffic or the configured runtime directory.
"""
import datetime
import os
import re
from pathlib import Path

from . import continuing_acceptance as ca
from .acceptance import validate_activation
from .files import digest, file_sha, private_root, read

SCHEMA = 'NEW_A_ACCEPTED_CANDIDATE_HANDOFF_V1'


def baseline(repo):
    """Read the actual current acceptance; never reinterpret it for another SHA."""
    repo = Path(repo).resolve()
    activation = private_root(repo) / 'activation.json'
    value = read(activation)
    validate_activation(value, repo)
    ca.require('continuing_acceptance' in value['owner_acceptance'],
               'formal continuing predecessor required')
    return dict(source_commit=ca.head(repo), activation_sha256=file_sha(activation),
                target=ca.target(repo), auth_source_hashes={
                    name: file_sha(repo / name) for name in ca.AUTH_FILES},
                previous_acceptance=value['owner_acceptance']['continuing_acceptance'])


def unchanged(repo, expected):
    ca.require(baseline(repo) == expected, 'operating baseline changed; do not promote')


def checked_deployment(source, destination, reader):
    ca.require(callable(reader), 'independent deployment reader required')
    value = reader()
    ca.require(isinstance(value, dict) and
               value.get('schema') in {'NEW_A_HOST_VERIFIED_DEPLOYMENT_V1',
                                       'NEW_A_HOST_VERIFIED_PRIVATE_CANDIDATE_PROBE_V1'} and
               value.get('source_commit') == source and value.get('target') == destination and
               value.get('synthetic') is not True and
               value.get('platform_signature_claimed') is False and
               re.fullmatch(r'[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12}',
                            str(value.get('version_id', ''))) and
               re.fullmatch(r'[a-f0-9]{64}', str(value.get('raw_receipt_sha256', ''))),
               'verified exact deployment unavailable')
    if value['schema'] == 'NEW_A_HOST_VERIFIED_DEPLOYMENT_V1':
        ca.require(value.get('deployment_succeeded') is True, 'actual deployment success required')
    else:
        # Separate future host capability; NEVER describe an upload/probe as a
        # deployment. No provider implementation or credentials are supplied.
        ca.require(value.get('deployment_succeeded') is False and
                   value.get('uploaded_only') is True and value.get('live_traffic_percent') == 0 and
                   value.get('normal_protected_probe') is True and
                   value.get('existing_owner_authorization') is True and
                   value.get('access_policy_unchanged') is True and
                   value.get('public_preview') is False,
                   'private pretraffic probe capability unavailable')
    ca.require(ca.timestamp(version_available_at(value)) <= ca.timestamp(value['observed_at']) <= ca.now(),
               'deployment observation time invalid')
    return value


def version_available_at(value):
    return value['deployed_at'] if value['schema'] == 'NEW_A_HOST_VERIFIED_DEPLOYMENT_V1' else value['version_available_at']


def same_deployment(first, latest):
    # A fresh GET can have a new observation time/receipt hash while observing
    # the same immutable provider version. Do not compare transport receipts.
    return all(first[key] == latest[key] for key in
               ['schema', 'source_commit', 'target', 'version_id']) and \
        version_available_at(first) == version_available_at(latest) and \
        ca.timestamp(latest['observed_at']) >= ca.timestamp(first['observed_at'])


def checked_measurements(plan, measurement_reader, raw_reader, deployment):
    ca.require(callable(measurement_reader) and callable(raw_reader),
               'independent measurement and raw receipt readers required')
    result = {}
    ca.require(set(plan['measurements']) == set(ca.PATHS), 'all existing measurements required')
    for kind, binding in plan['measurements'].items():
        measurement = measurement_reader(binding['id'])
        ca.require(digest(measurement) == binding['sha256'], 'actual host measurement changed')
        ca.verify_measurement(measurement, kind, plan['source_commit'],
                              plan['auth_source_hashes'], plan['target'])
        raw = raw_reader(kind)
        # These are safe fields from an independently obtained host receipt,
        # not an instruction to fabricate headers, cookies or a browser result.
        ca.require(isinstance(raw, dict) and raw.get('synthetic') is not True and
                   raw.get('receipt_sha256') == measurement['raw_receipt_sha256'] and
                   raw.get('source_commit') == plan['source_commit'] and
                   raw.get('target') == plan['target'] and
                   raw.get('version_id') == deployment['version_id'] and
                   measurement.get('deployment_version_id') == deployment['version_id'] and
                   raw.get('observed_at') == measurement['observed_at'] and
                   ca.timestamp(version_available_at(deployment)) <= ca.timestamp(raw['observed_at']) <= ca.now(),
                   'raw receipt source, version or observation mismatch')
        if kind == 'owner':
            ca.require(raw.get('owner_identity_verified') is True and
                       raw.get('source_kind') == 'EXISTING_LEGITIMATE_OWNER_SESSION' and
                       raw.get('document') == dict(path='/weak_early_beta_latest.html', status=200) and
                       raw.get('api') == dict(path='/api/cloud/new-a-finite/access', status=200,
                                              body=dict(authorized=True, strategy='A_BASE')),
                       'owner normal-response receipt unavailable')
        result[kind] = measurement
    return result


def prepare(operating_repo, candidate_repo, plan, *, primary_reader,
            measurement_reader, raw_reader, deployment_reader, decision_reader,
            authority, preflight, dry_run=True):
    """Use existing issue/apply ONLY in a separate, private candidate directory.

    Default is read-only. Candidate must already contain the byte-identical old
    activation and immutable audit chain. Do not copy credentials or daily DBs.
    Missing proof cannot advance the current source or update its acceptance.
    """
    operating_repo, candidate_repo = map(lambda p: Path(p).resolve(),
                                         (operating_repo, candidate_repo))
    ca.require(not (operating_repo.is_relative_to(candidate_repo) or
                    candidate_repo.is_relative_to(operating_repo)),
               'separate non-overlapping candidate required')
    before = baseline(operating_repo)
    source = ca.head(candidate_repo)
    ca.require(plan.get('scope') == ca.SCOPE and
               plan.get('decision') == 'CONTINUE_UNTIL_REVOKED_OR_BOUND_SOURCE_CHANGED' and
               plan.get('strategy') == 'A_BASE' and plan.get('virtual_only') is True and
               plan.get('nonowner_evidence_mode') == 'OWNER_DECISION_UNMEASURED' and
               'run_date' not in plan and 'expires_at' not in plan,
               'continuing decision scope not approved')
    ca.require(source != before['source_commit'] and source == plan['source_commit'],
               'distinct exact candidate source required')
    ca.require(ca.target(candidate_repo) == before['target'] == plan['target'] and
               plan['auth_source_hashes'] == before['auth_source_hashes'],
               'candidate changes protected target or auth sources')
    ca.verify_sources(candidate_repo, before['auth_source_hashes'])
    activation = private_root(candidate_repo) / 'activation.json'
    ca.require(file_sha(activation) == before['activation_sha256'] ==
               plan['expected_activation_sha256'], 'candidate baseline copy differs')
    ca.validate_evidence(read(activation)['owner_acceptance'], candidate_repo,
                         _historical_source=before['source_commit'])
    deployment = checked_deployment(source, before['target'], deployment_reader)
    measurements = checked_measurements(plan, measurement_reader, raw_reader, deployment)
    # Review actual primary and intent even for dry-run. No issuance is allowed
    # to treat a Slack message as a ChatGPT primary or widen its scope.
    owner = ca.primary_message(plan['owner_message'], primary_reader, authority)
    ca.require(callable(decision_reader), 'host operator intent review required')
    ca.checked_decision(decision_reader(owner['message_id']), owner, source,
                        before['target'], 'CONTINUING_DAILY_WITH_NONOWNER_UNMEASURED')
    until = ca.timestamp(plan['management_not_after'])
    ca.require(ca.now() < until <= ca.now() + datetime.timedelta(hours=1),
               'management authority expired or too broad')
    unchanged(operating_repo, before)
    identity = digest(dict(baseline=before, candidate=source,
                           deployment=deployment, measurements=measurements))
    result = dict(schema=SCHEMA, preparation_id=identity, candidate_source=source, operating_baseline=before,
                  deployment=deployment, measurement_hashes={k: digest(v) for k, v in measurements.items()},
                  not_after=until.isoformat(), operationally_promoted=False,
                  production_acceptance_written=False, synthetic=False,
                  platform_signature_claimed=False)
    if dry_run:
        return {**result, 'dry_run': True, 'candidate_acceptance_written': False}
    folder = private_root(candidate_repo) / 'release-handoffs' / identity
    folder.mkdir(parents=True, exist_ok=True)
    lock = folder.parent / 'prepare.lock'
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    started, stage = False, 'claim'
    try:
        os.write(fd, identity.encode()); os.fsync(fd)
        # Interrupted/failed preparation is not automatically retried. Keep all
        # grants/audits for reconciliation; never erase them to get another try.
        ca.immutable(folder / 'started.json', dict(schema=SCHEMA, **{
            'candidate_source': source, 'operating_baseline': before,
            'started_at': ca.now().isoformat()}))
        started, stage = True, 'issue'
        unchanged(operating_repo, before)
        frozen_by_id = {binding['id']: measurements[kind]
                        for kind, binding in plan['measurements'].items()}
        issued = ca.issue(candidate_repo, plan, primary_reader=primary_reader,
                          measurement_reader=lambda identifier: frozen_by_id[identifier],
                          decision_reader=decision_reader, authority=authority)
        stage = 'apply'
        applied = ca.apply(candidate_repo, issued, preflight=preflight,
                           previous_acceptance=before['previous_acceptance'])
        validate_activation(read(activation), candidate_repo)
        # Fail closed if another release replaced the actual observed version.
        stage = 'readback'
        ca.require(same_deployment(deployment, checked_deployment(source, before['target'], deployment_reader)),
                   'deployment changed during preparation')
        unchanged(operating_repo, before)
        result.update(dry_run=False, candidate_acceptance_written=True,
                      candidate_activation_sha256=file_sha(activation),
                      issued=issued, application=applied)
        ca.immutable(folder / 'ready.json', result)
        return result
    except Exception as error:
        if started:
            # Exception class and stage only: do not persist a remote body,
            # command output or arbitrary error string that might contain data.
            ca.immutable(folder / 'failed.json', dict(schema=SCHEMA, stage=stage,
                         exception_type=type(error).__name__, failed_at=ca.now().isoformat(),
                         operationally_promoted=False, production_acceptance_written=False))
        raise
    finally:
        os.close(fd)
        if lock.exists() and lock.read_text() == identity:
            lock.unlink()


def verify_ready(operating_repo, candidate_repo, receipt, *, deployment_reader):
    """Read-only prerequisite; no function here changes the operating directory."""
    ca.require(receipt.get('schema') == SCHEMA and receipt.get('dry_run') is False and
               receipt.get('candidate_acceptance_written') is True and
               receipt.get('operationally_promoted') is False and
               receipt.get('production_acceptance_written') is False and
               receipt.get('synthetic') is not True and
               receipt.get('platform_signature_claimed') is False,
               'completed candidate receipt required')
    ca.require(ca.now() < ca.timestamp(receipt['not_after']), 'handoff management authority expired')
    unchanged(operating_repo, receipt['operating_baseline'])
    candidate_repo = Path(candidate_repo).resolve()
    ca.require(re.fullmatch(r'[a-f0-9]{64}', str(receipt.get('preparation_id', ''))),
               'private preparation reference required')
    ready = private_root(candidate_repo) / 'release-handoffs' / receipt['preparation_id'] / 'ready.json'
    ca.require(ready.is_file() and read(ready) == receipt, 'immutable ready receipt missing or changed')
    ca.require(ca.head(candidate_repo) == receipt['candidate_source'] and
               file_sha(private_root(candidate_repo) / 'activation.json') ==
               receipt['candidate_activation_sha256'], 'prepared candidate changed')
    validate_activation(read(private_root(candidate_repo) / 'activation.json'), candidate_repo)
    ca.require(same_deployment(receipt['deployment'], checked_deployment(receipt['candidate_source'],
                                 receipt['operating_baseline']['target'], deployment_reader)),
               'observed deployed version changed')
    return dict(ok=True, source_commit=receipt['candidate_source'],
                operationally_promoted=False, production_acceptance_written=False)


def handoff_binding(operating_repo, candidate_repo, receipt, *, deployment_reader):
    """Opaque safe binding for a trusted CI/runtime coordinator, not a signature."""
    verify_ready(operating_repo, candidate_repo, receipt, deployment_reader=deployment_reader)
    return dict(schema='NEW_A_RELEASE_CANDIDATE_BINDING_V1',
                source_commit=receipt['candidate_source'], target=receipt['operating_baseline']['target'],
                worker_version_id=receipt['deployment']['version_id'],
                acceptance_sha256=receipt['issued']['acceptance']['sha256'],
                activation_sha256=receipt['candidate_activation_sha256'],
                preparation_sha256=digest(receipt), not_after=receipt['not_after'],
                evidence_mode='PRIVATE_PRETRAFFIC_PROBE' if
                receipt['deployment']['schema'] == 'NEW_A_HOST_VERIFIED_PRIVATE_CANDIDATE_PROBE_V1'
                else 'ALREADY_DEPLOYED_VERSION', platform_signature_claimed=False)
