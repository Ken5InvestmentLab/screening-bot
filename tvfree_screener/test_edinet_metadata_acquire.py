import io
import json
from datetime import date

import pytest

import tvfree_screener.edinet_metadata_acquire as m


class _Resp:
    status = 200
    def __init__(self, raw): self._raw = raw
    def read(self): return self._raw
    def __enter__(self): return self
    def __exit__(self, *args): return False


def test_acquire_day_uses_v2_required_query(monkeypatch):
    seen = {}
    raw = json.dumps({"metadata": {"status": "200"}, "results": []}).encode()
    def fake(req, timeout):
        seen["url"] = req.full_url
        seen["timeout"] = timeout
        return _Resp(raw)
    monkeypatch.setattr(m.urllib.request, "urlopen", fake)
    out = m.acquire_day(date(2024, 1, 2), api_key="secret-key", timeout=7)
    assert out == raw
    assert "date=2024-01-02" in seen["url"]
    assert "type=2" in seen["url"]
    assert "Subscription-Key=secret-key" in seen["url"]
    assert seen["timeout"] == 7


def test_acquire_day_fails_closed_on_bad_payload(monkeypatch):
    monkeypatch.setattr(m.urllib.request, "urlopen", lambda *a, **k: _Resp(b"{}"))
    with pytest.raises(ValueError, match="malformed"):
        m.acquire_day(date(2024, 1, 2), api_key="k")


def test_acquire_range_resumes_without_refetch(tmp_path, monkeypatch):
    existing = tmp_path / "2024-01-01.json"
    existing.write_text('{"metadata":{"status":"200"},"results":[]}')
    calls = []
    def fake(day, *, api_key, timeout=60):
        calls.append(day.isoformat())
        return b'{"metadata":{"status":"200"},"results":[]}'
    monkeypatch.setattr(m, "acquire_day", fake)
    result = m.acquire_range(tmp_path, start="2024-01-01", end="2024-01-02", api_key="k", sleep_seconds=0)
    assert result == {"fetched": 1, "skipped": 1}
    assert calls == ["2024-01-02"]
    assert (tmp_path / "2024-01-02.json").exists()


def test_api_key_required():
    with pytest.raises(ValueError, match="API key"):
        m.acquire_day(date(2024, 1, 1), api_key="")
