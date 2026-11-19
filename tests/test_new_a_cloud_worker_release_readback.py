import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from weak_early_beta.new_a import cloud_worker_release_readback as reader
from weak_early_beta.new_a.files import atomic_write


VERSION = "00000000-0000-4000-8000-000000000019"
DEPLOYMENT = "10000000-0000-4000-8000-000000000019"
SOURCE = "a" * 40
ACTIVE = "b" * 64
TARGET = {
    "service": "tentei-kyokuchi-cloud", "binding": "CLOUD_DB",
    "database_name": "tentei-cloud-settings",
    "database_id": "e0cdb3a7-b682-4db8-96ac-f2afcc9c23cb",
}
APPROVED = {
    "schema": reader.RUNTIME_RELEASE_SCHEMA, "version_id": VERSION, "source_commit": SOURCE,
    "worker": TARGET["service"], "database": TARGET["database_name"], "tag": "cloud-deploy-fixture",
    "ci_run_id": 1234, "build_input_sha256": "c" * 64, "policy_sha256": "d" * 64,
}


def payload(deployment_id=DEPLOYMENT, versions=None, **other):
    return json.dumps({
        "id": deployment_id, "created_on": "2026-01-01T00:00:00Z", "strategy": "percentage",
        "versions": [{"version_id": VERSION, "percentage": 100}] if versions is None else versions,
        **other,
    }).encode()


class CloudWorkerReleaseReadbackTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.repo = Path(folder.name).resolve()
        atomic_write(self.repo / ".cache/weak_early_beta/daily-runner.config.json", {"nodePath": "fixture-node"})
        for name, value in {"target": TARGET, "head": SOURCE}.items():
            patcher = patch.object(reader.acceptance, name, return_value=value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.addMock("deployment_status", return_value=payload(author_email="synthetic@example.invalid"))
        self.addMock("WranglerD1")
        self.addMock("read_active_metadata", return_value=({"revision": 4}, {}, ACTIVE))
        self.addMock("observe_normal_response", return_value="e" * 64)

    def addMock(self, name, **kwargs):
        patcher = patch.object(reader, name, **kwargs)
        setattr(self, name, patcher.start())
        self.addCleanup(patcher.stop)

    def test_observes_two_deployment_samples_and_nonce_bound_primary_generation(self):
        result = reader.read_active_production_release(self.repo, APPROVED)
        self.assertEqual(result["deployment_id"], DEPLOYMENT)
        self.assertEqual(result["version_id"], VERSION)
        self.assertEqual(result["live_traffic_percent"], 100)
        self.assertEqual(result["active_owner_sha256"], ACTIVE)
        self.assertNotIn("example.invalid", str(result))
        self.assertEqual(self.deployment_status.call_count, 2)
        self.assertEqual(self.read_active_metadata.call_count, 2)
        self.assertTrue(self.WranglerD1.call_args.kwargs["require_primary"])
        self.observe_normal_response.assert_called_once_with(
            source=SOURCE, version_id=VERSION, build_input_sha256="c" * 64,
            policy_sha256="d" * 64, active=ACTIVE,
        )

    def test_refused_or_split_deployment_blocks_before_reading_d1(self):
        self.deployment_status.side_effect = PermissionError("Production deployment read refused")
        with self.assertRaises(PermissionError):
            reader.read_active_production_release(self.repo, APPROVED)
        self.deployment_status.side_effect = None
        self.deployment_status.return_value = payload(versions=[{"version_id": VERSION, "percentage": 99}])
        with self.assertRaisesRegex(ValueError, "single active version"):
            reader.read_active_production_release(self.repo, APPROVED)
        self.WranglerD1.assert_not_called()

    def test_known_version_reuse_under_a_changed_deployment_is_not_confirmation(self):
        self.deployment_status.side_effect = [payload(), payload("20000000-0000-4000-8000-000000000019")]
        with self.assertRaisesRegex(ValueError, "deployment changed"):
            reader.read_active_production_release(self.repo, APPROVED)

    def test_owner_generation_drift_stops_before_the_second_provider_read(self):
        self.read_active_metadata.side_effect = [
            ({"revision": 4}, {}, ACTIVE), ({"revision": 5}, {}, "f" * 64),
        ]
        with self.assertRaisesRegex(ValueError, "generation changed"):
            reader.read_active_production_release(self.repo, APPROVED)
        self.deployment_status.assert_called_once()
