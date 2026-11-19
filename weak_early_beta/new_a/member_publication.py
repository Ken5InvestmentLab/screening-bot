"""Publish the member projection of the current, verified ordinary owner generation."""

from pathlib import Path
import subprocess
import tempfile

from .continuing_transition import ordinary_runtime_release
from .files import atomic_write, digest, file_sha, private_root, read
from .member_publisher import import_member_projection, read_member_marker
from .operational_admission import now, observe_normal_response, read_active_metadata
from .publisher import logical_manifest, validate_manifest


def ready_identity(row, manifest):
    return {
        'status': 'READY',
        'dataset_id': row['dataset_id'],
        'revision': row['revision'],
        'as_of': manifest['as_of'],
        'source_version': row['source_version'],
    }


def current_owner_input(root, owner_db):
    run = read(root / 'latest-run.json')
    publication = read(root / 'latest-publication.json')
    if (publication.get('schema') != 'NEW_A_PRIVATE_PUBLICATION_RECEIPT_V1'
            or not all(publication.get(key) is True for key in
                       ('published', 'active_readback_verified', 'existing_owner_gate_verified'))
            or 'delayed_recovery' in publication or 'operational_admission' in publication
            or run.get('strategy') != 'A_BASE' or run.get('detection_executed') is not True
            or run.get('dry_run') is not False or 'delayed_recovery' in run):
        raise ValueError('Verified ordinary owner publication required for the member view')
    row, manifest, active = read_active_metadata(owner_db)
    validate_manifest(manifest)
    if (any(publication.get(key) != row[key] for key in
            ('dataset_id', 'revision', 'source_version', 'manifest_sha256'))
            or publication.get('as_of') != manifest.get('as_of')
            or run.get('latest_session') != manifest['as_of']
            or publication.get('snapshot_sha256') != manifest.get('daily_snapshot_sha256')
            or run.get('snapshot_sha256') != publication['snapshot_sha256']
            or run.get('source_version') != publication['source_version']):
        raise ValueError('Active owner generation differs from the confirmed publication')
    bundle = Path(run['bundle_directory'])
    if not bundle.is_absolute() or bundle.resolve() != bundle or not bundle.is_relative_to(root / 'runs'):
        raise ValueError('Member projection requires the retained private run bundle')
    return row, manifest, active, bundle


def publish_current_member_view(repo, owner_db, member_db, *, node):
    """Run only the data publication stage. Never compute detection or send notifications."""
    repo = Path(repo).resolve()
    root = private_root(repo)
    release = ordinary_runtime_release(repo)
    if release is None:
        raise ValueError('Exact ordinary Worker approval required for member publication')
    row, manifest, active, bundle = current_owner_input(root, owner_db)
    original = ready_identity(row, manifest)

    def verify_owner_response():
        return observe_normal_response(
            source=release['source_commit'], version_id=release['version_id'],
            build_input_sha256=release['build_input_sha256'], policy_sha256=release['policy_sha256'],
            active=active,
        )

    response_sha = verify_owner_response()
    work = root / 'member-publication'
    work.mkdir(exist_ok=True)
    if work.resolve() != work:
        raise ValueError('Member projection work directory leaves the private root')
    with tempfile.TemporaryDirectory(prefix='projection-', dir=work) as directory:
        workdir = Path(directory)
        proof = workdir / 'owner-ready-proof.json'
        atomic_write(proof, {
            'schema': 'NEW_A_OPERATIONAL_OBSERVATION_V1',
            'observed_at': now().isoformat(),
            'source_commit': release['source_commit'],
            'version_id': release['version_id'],
            'active_as_of': original['as_of'],
            'active_dataset_id': original['dataset_id'],
            'active_revision': original['revision'],
            'active_source_version': original['source_version'],
            'active_manifest_sha256': row['manifest_sha256'],
            'active_logical_manifest_sha256': digest(logical_manifest(manifest)),
            'd1_active_sha256': active,
            'raw_response_sha256': response_sha,
            'owner_http_observed': False,
        })
        output = workdir / 'projection'
        builder = repo / 'weak-early-beta-gate/scripts/prepare-new-a-member-projection.cjs'
        build = subprocess.run(
            [node, str(builder), '--bundle', str(bundle), '--ready-proof', str(proof),
             '--ready-proof-sha256', file_sha(proof), '--out', str(output)],
            cwd=repo, capture_output=True, timeout=180,
        )
        if build.returncode != 0:
            raise ValueError('Verified member projection build failed')
        projection_receipt_path = output / 'receipt.json'
        receipt_sha = file_sha(projection_receipt_path)
        if read(projection_receipt_path).get('owner_readback_sha256') != file_sha(proof):
            raise ValueError('Member projection receipt differs from the verified generation')

        def official_ready():
            current, current_manifest, current_active = read_active_metadata(owner_db)
            return ready_identity(current, current_manifest) if current_active == active else None

        if ordinary_runtime_release(repo) != release:
            raise ValueError('Ordinary Worker approval changed before member publication')
        result = import_member_projection(
            member_db, output, read_official_ready=official_ready, receipt_sha256=receipt_sha,
            expected_previous=read_member_marker(member_db),
        )
        if result['source'] != original or result['status'] not in ('activated', 'already_active'):
            raise ValueError('Member generation activation was not confirmed')
        verify_owner_response()
        if ordinary_runtime_release(repo) != release or official_ready() != original:
            raise ValueError('Approved Worker or owner generation changed after member publication')
        if read_member_marker(member_db) != {'identity': result['identity'], 'digest': result['digest']}:
            raise ValueError('Member generation changed after activation')

    receipt = {
        'schema': 'NEW_A_MEMBER_PUBLICATION_V1',
        'published': True,
        'active_readback_verified': True,
        'source': original,
        'projection_sha256': result['digest'],
        'parts': result['parts'],
        'worker_version_id': release['version_id'],
        'same_generation_replay': result['status'] == 'already_active',
    }
    atomic_write(root / 'latest-member-publication.json', receipt)
    return receipt
