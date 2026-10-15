"""Bounded retries for Cloud's read-only acquisition requests."""

from __future__ import annotations

import errno
import math
import re
import time
from typing import Any, Callable

import requests


TRANSIENT_HTTP_STATUS = {429, 500, 502, 503, 504}
TRANSIENT_CURL_CODES = {5, 6, 7, 18, 28, 52, 55, 56, 92}


def permanent_network_error(error: Any) -> bool:
    """Recognize swallowed TLS/HTTP rejection diagnostics that must stop now."""
    if isinstance(error, requests.exceptions.SSLError):
        return True
    if isinstance(error, requests.exceptions.HTTPError):
        return not transient_network_error(error)
    message = str(error)
    curl = re.search(r"curl:\s*\((\d+)\)", message, re.IGNORECASE)
    if curl and int(curl.group(1)) in {51, 58, 60, 77, 83, 90, 91}:
        return True
    return bool(re.search(
        r"\b(?:SSLError|CurlSSLError|SSLCertVerificationError)\b|certificate verify failed|"
        r"\bHTTP(?:\s+Error|\s+status)?[\s:'\"]+(?:400|401|403|404)\b|"
        r"\b(?:400|401|403|404)\s+Client\s+Error\b",
        message, re.IGNORECASE,
    ))


def transient_network_error(error: Any) -> bool:
    """Recognize transport failures, including yfinance's saved error strings.

    Missing prices/actions, malformed responses, TLS verification and ordinary
    HTTP authorization/not-found responses are never a transport retry signal.
    """
    if isinstance(error, requests.exceptions.SSLError):
        return False
    if isinstance(error, requests.exceptions.HTTPError):
        return getattr(error.response, "status_code", None) in TRANSIENT_HTTP_STATUS
    if type(error).__name__ == "YFRateLimitError":
        return True
    if isinstance(error, (requests.exceptions.Timeout, requests.exceptions.ConnectionError,
                          TimeoutError, ConnectionError)):
        return True
    if isinstance(error, OSError):
        if getattr(error, "winerror", None) in {10048, 10055, 10054, 10060, 10061, 10065}:
            return True
        if error.errno in {errno.ENOBUFS, errno.EADDRINUSE, errno.ECONNRESET,
                           errno.ECONNREFUSED, errno.ETIMEDOUT, errno.ENETUNREACH,
                           errno.ENETDOWN, errno.EHOSTUNREACH}:
            return True
    code = getattr(error, "code", None)
    if type(error).__module__.startswith("curl_cffi") and code in TRANSIENT_CURL_CODES:
        return True
    message = str(error)
    curl = re.search(r"curl:\s*\((\d+)\)", message, re.IGNORECASE)
    if curl and int(curl.group(1)) in TRANSIENT_CURL_CODES:
        return True
    if re.search(r"WinError\s+(?:10048|10055|10054|10060|10061|10065)\b", message):
        return True
    return bool(re.search(r"\b(?:YFRateLimitError|ConnectTimeout|ReadTimeout|ConnectionResetError|ConnectionRefusedError)\b", message))


def retry_get(get: Callable[..., Any], url: str, **kwargs: Any) -> Any:
    """Retry only this GET, at most three times; never retry parsing or writes."""
    for attempt in range(3):
        response = None
        try:
            response = get(url, **kwargs)
            response.raise_for_status()
            return response
        except Exception as error:
            try:
                if not transient_network_error(error) or attempt == 2:
                    raise
                delay = float(2 ** attempt)
                retry_after = getattr(response, "headers", {}).get("Retry-After")
                if retry_after is not None:
                    try:
                        provider_delay = float(retry_after)
                    except (TypeError, ValueError):
                        raise error
                    # Reject invalid/long deadlines before max(): max(1, nan)
                    # can silently keep 1 and retry earlier than the provider.
                    if not math.isfinite(provider_delay) or not 0 <= provider_delay <= 60:
                        raise error
                    delay = max(delay, provider_delay)
            finally:
                if response is not None:
                    close = getattr(response, "close", None)
                    if close is not None:
                        try:
                            close()
                        except Exception:
                            # Cleanup must not hide the original HTTP failure.
                            pass
            time.sleep(delay)
