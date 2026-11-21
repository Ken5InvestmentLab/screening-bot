"""Isolated notification tests: no optimizer, credentials, or network access."""
import ast
import contextlib
import io
import json
import os
from pathlib import Path
import socket
import tempfile
import unittest
from unittest import mock
import urllib.error

ROOT = Path(__file__).resolve().parents[1]
TEST_ENDPOINT = "https://example.invalid/notification-test"


def load_notification_code(filename, names, environment):
    source = (ROOT / filename).read_text(encoding="utf-8")
    tree = ast.parse(source)
    wanted = {"DISCORD_WEBHOOK_URL", "APPROVAL_WEBHOOK_URL"}
    nodes = [
        node for node in tree.body
        if (isinstance(node, ast.FunctionDef) and node.name in names)
        or (isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id in wanted
            for target in node.targets
        ))
    ]
    namespace = {"os": os, "json": json}
    with mock.patch.dict(os.environ, environment, clear=True):
        exec(compile(ast.Module(body=nodes, type_ignores=[]), filename, "exec"), namespace)
    return namespace


class WebhookEnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.network = mock.patch.object(socket, "socket", side_effect=AssertionError("network forbidden"))
        self.network.start()
        self.addCleanup(self.network.stop)

    def optimizer(self, environment=None):
        return load_notification_code("optimize_screener.py", {
            "_post_discord_webhook", "_queue_or_post_discord_approval",
            "flush_discord_approval_notices",
        }, environment or {})

    def monitor(self, environment=None):
        return load_notification_code("monitor_live.py", {"notify_discord"}, environment or {})

    def test_missing_and_blank_monitor_configuration_never_requests(self):
        for environment in [{}, {"DISCORD_WEBHOOK_URL": " \t "}]:
            with self.subTest(environment=bool(environment)), mock.patch("urllib.request.urlopen") as send:
                ns = self.monitor(environment)
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertFalse(ns["notify_discord"]("message"))
                send.assert_not_called()

    def test_monitor_uses_trimmed_environment_and_preserves_payload(self):
        ns = self.monitor({"DISCORD_WEBHOOK_URL": " " + TEST_ENDPOINT + " "})
        with mock.patch("urllib.request.urlopen") as send:
            self.assertTrue(ns["notify_discord"]("message"))
        request = send.call_args.args[0]
        self.assertEqual(request.full_url, TEST_ENDPOINT)
        self.assertEqual(json.loads(request.data), {"content": "message"})
        self.assertEqual(request.method, "POST")

    def test_monitor_failure_does_not_log_request_url(self):
        ns = self.monitor({"DISCORD_WEBHOOK_URL": TEST_ENDPOINT})
        output = io.StringIO()
        with mock.patch("urllib.request.urlopen", side_effect=RuntimeError(TEST_ENDPOINT)), contextlib.redirect_stdout(output):
            self.assertFalse(ns["notify_discord"]("message"))
        self.assertNotIn(TEST_ENDPOINT, output.getvalue())

    def test_missing_optimizer_endpoints_skip_direct_queue_and_flush(self):
        for environment in [{}, {"DISCORD_WEBHOOK_URL": " ", "DISCORD_APPROVAL_WEBHOOK_URL": "\t"}]:
            ns = self.optimizer(environment)
            with tempfile.TemporaryDirectory(dir=ROOT) as tmp, mock.patch("urllib.request.urlopen") as send, contextlib.redirect_stdout(io.StringIO()):
                outbox = Path(tmp) / "must-not-be-created"
                with mock.patch.dict(os.environ, {"DISCORD_APPROVAL_NOTICE_DIR": str(outbox)}, clear=True):
                    self.assertFalse(ns["_post_discord_webhook"](ns["DISCORD_WEBHOOK_URL"], {"content": "message"}))
                    self.assertFalse(ns["_queue_or_post_discord_approval"]({"content": "message"}))
                    self.assertEqual(ns["flush_discord_approval_notices"](), 0)
                self.assertFalse(outbox.exists())
                send.assert_not_called()

    def test_optimizer_uses_separate_environment_endpoints(self):
        ns = self.optimizer({"DISCORD_WEBHOOK_URL": " " + TEST_ENDPOINT + " ", "DISCORD_APPROVAL_WEBHOOK_URL": " " + TEST_ENDPOINT + "/approval "})
        self.assertEqual(ns["DISCORD_WEBHOOK_URL"], TEST_ENDPOINT)
        self.assertEqual(ns["APPROVAL_WEBHOOK_URL"], TEST_ENDPOINT + "/approval")

    def test_optimizer_mock_json_and_attachment_posts(self):
        ns = self.optimizer()
        payload = {"content": "message"}
        for attachment in [None, {"filename": "comparison.xlsx", "content": b"fixture"}]:
            with self.subTest(attachment=bool(attachment)), mock.patch("urllib.request.urlopen") as send, contextlib.redirect_stdout(io.StringIO()):
                send.return_value.__enter__.return_value.status = 204
                self.assertTrue(ns["_post_discord_webhook"](TEST_ENDPOINT, payload, attachment))
                request = send.call_args.args[0]
                self.assertEqual(request.full_url, TEST_ENDPOINT)
                self.assertEqual(request.method, "POST")
                if attachment:
                    self.assertIn(b"fixture", request.data)
                    self.assertIn(b"comparison.xlsx", request.data)
                else:
                    self.assertEqual(json.loads(request.data), payload)

    def test_optimizer_failures_do_not_log_url_or_response_body(self):
        ns = self.optimizer()
        for failure in [RuntimeError(TEST_ENDPOINT), urllib.error.HTTPError(TEST_ENDPOINT, 401, "denied", {}, io.BytesIO(TEST_ENDPOINT.encode()))]:
            output = io.StringIO()
            with self.subTest(kind=type(failure).__name__), mock.patch("urllib.request.urlopen", side_effect=failure), contextlib.redirect_stdout(output):
                self.assertFalse(ns["_post_discord_webhook"](TEST_ENDPOINT, {"content": "message"}))
            self.assertNotIn(TEST_ENDPOINT, output.getvalue())
            if isinstance(failure, urllib.error.HTTPError):
                failure.close()

    def test_approval_queue_and_flush_route_to_approval_endpoint(self):
        ns = self.optimizer({"DISCORD_APPROVAL_WEBHOOK_URL": TEST_ENDPOINT + "/approval"})
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp, mock.patch.dict(os.environ, {"DISCORD_APPROVAL_NOTICE_DIR": tmp}, clear=True), contextlib.redirect_stdout(io.StringIO()):
            post = mock.Mock(return_value=True)
            ns["_post_discord_webhook"] = post
            self.assertTrue(ns["_queue_or_post_discord_approval"]({"content": "queued"}))
            post.assert_not_called()
            self.assertEqual(ns["flush_discord_approval_notices"](), 1)
            self.assertEqual(post.call_args.args[0], TEST_ENDPOINT + "/approval")
            self.assertEqual(post.call_args.args[1], {"content": "queued"})

    def test_notification_prints_do_not_interpolate_raw_exceptions(self):
        tree = ast.parse((ROOT / "optimize_screener.py").read_text(encoding="utf-8"))
        for function in tree.body:
            if not isinstance(function, ast.FunctionDef) or not ("discord" in function.name or "notif" in function.name):
                continue
            for call in ast.walk(function):
                if isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id == "print":
                    for node in ast.walk(call):
                        if isinstance(node, ast.FormattedValue):
                            self.assertFalse(any(isinstance(part, ast.Name) and part.id == "body" for part in ast.walk(node.value)), function.name)
                            self.assertFalse(isinstance(node.value, ast.Name) and node.value.id in {"e", "exc"}, function.name)


if __name__ == "__main__":
    unittest.main()
