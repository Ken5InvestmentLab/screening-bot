"""Acquisition retries never replay parsing, snapshots, or daily scoring."""

import unittest
from unittest.mock import Mock, patch

import requests

from weak_early_beta.network import permanent_network_error, retry_get, transient_network_error


class NetworkTests(unittest.TestCase):
    def test_swallowed_certificate_and_authorization_failures_are_terminal(self):
        for error in ("SSLError('curl: (60) certificate verify failed')",
                      "HTTPError('HTTP Error 404: Not Found')", "HTTPError('403 Client Error: Forbidden')"):
            with self.subTest(error=error):
                self.assertTrue(permanent_network_error(error))
        for error in ("curl: (7) failed to connect", "YFPricesMissingError('no price data')"):
            with self.subTest(error=error):
                self.assertFalse(permanent_network_error(error))

    def test_only_transport_and_temporary_http_errors_are_retryable(self):
        for error in (requests.ConnectionError("socket unavailable"), requests.Timeout("slow"),
                      OSError(10048, "socket"), "ConnectionError('curl: (7) failed to connect')",
                      "[WinError 10048] socket already used", "YFRateLimitError('rate limited')"):
            with self.subTest(error=error):
                # Windows errors are represented by winerror, not errno, when
                # created by the OS. The message form is tested separately.
                if isinstance(error, OSError) and error.errno == 10048:
                    error.winerror = 10048
                self.assertTrue(transient_network_error(error))
        for error in (ValueError("bad schema"), RuntimeError("unknown"),
                      requests.exceptions.SSLError("certificate verification failed"),
                      "YFPricesMissingError('possibly delisted')", "curl: (60) certificate error"):
            with self.subTest(error=error):
                self.assertFalse(transient_network_error(error))
        for status in (400, 401, 403, 404, 429, 500, 502, 503, 504):
            response = requests.Response()
            response.status_code = status
            error = requests.HTTPError("http failure", response=response)
            self.assertEqual(transient_network_error(error), status >= 429)

    @patch("weak_early_beta.network.time.sleep")
    def test_get_recovers_same_request_once_and_retains_parameters(self, sleep):
        response = Mock()
        get = Mock(side_effect=[requests.ConnectionError("[WinError 10048] exhausted"), response])
        self.assertIs(retry_get(get, "https://example.test/page", timeout=60), response)
        self.assertEqual(get.call_count, 2)
        self.assertEqual(get.call_args_list[0], get.call_args_list[1])
        sleep.assert_called_once_with(1)

    @patch("weak_early_beta.network.time.sleep")
    def test_get_exhaustion_raises_original_cause_without_extra_attempts(self, sleep):
        errors = [requests.Timeout(str(i)) for i in range(3)]
        get = Mock(side_effect=errors)
        with self.assertRaises(requests.Timeout) as caught:
            retry_get(get, "https://example.test/page", timeout=60)
        self.assertIs(caught.exception, errors[-1])
        self.assertEqual(get.call_count, 3)
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [1, 2])

    @patch("weak_early_beta.network.time.sleep")
    def test_auth_unknown_and_long_provider_wait_stop_immediately(self, sleep):
        for status, headers in ((403, {}), (404, {}), (429, {"Retry-After": "3600"})):
            response = requests.Response()
            response.status_code = status
            response.headers.update(headers)
            get = Mock(return_value=response)
            with self.assertRaises(requests.HTTPError):
                retry_get(get, "https://example.test/page")
            get.assert_called_once()
        get = Mock(side_effect=ValueError("invalid request"))
        with self.assertRaises(ValueError):
            retry_get(get, "https://example.test/page")
        get.assert_called_once()
        sleep.assert_not_called()

    @patch("weak_early_beta.network.time.sleep")
    def test_rate_limit_honors_short_retry_after(self, sleep):
        limited = requests.Response()
        limited.status_code = 429
        limited.headers["Retry-After"] = "5"
        limited.close = Mock()
        ok = requests.Response()
        ok.status_code = 200
        get = Mock(side_effect=[limited, ok])
        self.assertIs(retry_get(get, "https://example.test/page"), ok)
        sleep.assert_called_once_with(5)
        limited.close.assert_called_once()

    @patch("weak_early_beta.network.time.sleep")
    def test_invalid_provider_delays_fail_without_sleep_and_close_response(self, sleep):
        for value in ("nan", "inf", "-1", "invalid", "61"):
            with self.subTest(value=value):
                response = requests.Response()
                response.status_code = 429
                response.headers["Retry-After"] = value
                response.close = Mock()
                get = Mock(return_value=response)
                with self.assertRaises(requests.HTTPError):
                    retry_get(get, "https://example.test/page")
                get.assert_called_once()
                response.close.assert_called_once()
        sleep.assert_not_called()

    @patch("weak_early_beta.network.time.sleep")
    def test_final_http_failure_closes_each_response_and_preserves_http_error(self, sleep):
        responses = [requests.Response() for _ in range(3)]
        for response in responses:
            response.status_code = 503
            response.close = Mock(side_effect=RuntimeError("cleanup failed"))
        get = Mock(side_effect=responses)
        with self.assertRaises(requests.HTTPError) as caught:
            retry_get(get, "https://example.test/page")
        self.assertIs(caught.exception.response, responses[-1])
        for response in responses:
            response.close.assert_called_once()
        self.assertEqual(sleep.call_count, 2)


if __name__ == "__main__":
    unittest.main()
