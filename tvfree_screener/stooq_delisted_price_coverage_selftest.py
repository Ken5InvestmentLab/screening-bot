#!/usr/bin/env python3
"""Synthetic checks for the TEST-only Stooq delisted-price probe."""
from __future__ import annotations

import pandas as pd

import stooq_delisted_price_coverage as s


class FakeResponse:
    def __init__(self, text: str, status_code: int = 200):
        self.text = text
        self.status_code = status_code


class FakeSession:
    def __init__(self, responses: dict[str, FakeResponse]):
        self.responses = responses
        self.requested: list[dict] = []

    def get(self, url, params=None, timeout=None, headers=None):
        self.requested.append(dict(params or {}))
        ticker = str((params or {}).get("s", ""))
        return self.responses[ticker]

    def close(self):
        pass


def good_csv(last_date: str = "2024-06-28") -> str:
    end = pd.Timestamp(last_date)
    dates = pd.bdate_range(end=end, periods=12)
    rows = ["Date,Open,High,Low,Close,Volume"]
    for i, day in enumerate(dates):
        px = 100 + i
        rows.append(f"{day:%Y-%m-%d},{px},{px+2},{px-2},{px+1},{10000+i}")
    return "\n".join(rows)


def main() -> None:
    # Deterministic sample must exclude quarantined and 2026 rows and balance years.
    candidates = pd.DataFrame([
        {"code": "1001", "delisting_date": "2022-05-01", "identity_quarantined": False},
        {"code": "1002", "delisting_date": "2022-08-01", "identity_quarantined": False},
        {"code": "2001", "delisting_date": "2023-05-01", "identity_quarantined": False},
        {"code": "3001", "delisting_date": "2024-05-01", "identity_quarantined": False},
        {"code": "4001", "delisting_date": "2025-05-01", "identity_quarantined": False},
        {"code": "5001", "delisting_date": "2025-06-01", "identity_quarantined": True},
        {"code": "6001", "delisting_date": "2026-05-01", "identity_quarantined": False},
    ])
    a = s.select_deterministic_pre2026_sample(candidates, sample_size=4)
    b = s.select_deterministic_pre2026_sample(candidates, sample_size=4)
    assert a[["code", "delisting_date"]].astype(str).equals(b[["code", "delisting_date"]].astype(str))
    assert set(pd.to_datetime(a["delisting_date"]).dt.year) == {2022, 2023, 2024, 2025}
    assert "5001" not in set(a["code"])
    assert "6001" not in set(a["code"])

    # Authentication and quota responses must be errors, never missing coverage.
    assert s._classify_stooq_text("Get your apikey: https://stooq.com/q/d/?get_apikey")[0] == "probe_error_auth"
    assert s._classify_stooq_text("Daily request quota exceeded")[0] == "probe_error_rate_limit"
    assert s._classify_stooq_text("No data")[0] is None

    delist = pd.Timestamp("2024-06-30")
    assessed = s.assess_stooq_ohlcv(s.parse_stooq_csv(good_csv()), delist)
    assert assessed["usable_near_delist"] is True
    assert assessed["ohlcv_columns_complete"] is True
    assert assessed["usable_near_delist_ohlcv"] is True
    assert assessed["last_price_gap_days"] <= s.MAX_LAST_PRICE_GAP_DAYS

    # A price row after official delisting is suspicious and must fail acceptance.
    post = good_csv() + "\n2024-07-02,120,122,118,121,15000"
    assessed_post = s.assess_stooq_ohlcv(s.parse_stooq_csv(post), delist)
    assert assessed_post["coverage_status"] == "suspicious_post_delist_data"
    assert assessed_post["usable_near_delist_ohlcv"] is False

    # Missing Volume must not satisfy the OHLCV gate even when prices are near delisting.
    no_volume = good_csv().replace(",Volume", "").replace(",10000", "").replace(",10001", "")
    # Build a clean no-volume frame to avoid depending on string replacement details.
    frame = s.parse_stooq_csv(good_csv()).drop(columns=["volume"])
    assessed_no_volume = s.assess_stooq_ohlcv(frame, delist)
    assert assessed_no_volume["ohlcv_columns_complete"] is False
    assert assessed_no_volume["usable_near_delist_ohlcv"] is False
    assert assessed_no_volume["coverage_status"] == "partial_missing_ohlcv"

    # End-to-end probe keeps auth/missing distinct and never persists the key in errors.
    live_candidates = pd.DataFrame([
        {"code": "1111", "ticker": "1111.T", "delisting_date": pd.Timestamp("2024-06-30"), "identity_quarantined": False},
        {"code": "2222", "ticker": "2222.T", "delisting_date": pd.Timestamp("2024-06-30"), "identity_quarantined": False},
        {"code": "3333", "ticker": "3333.T", "delisting_date": pd.Timestamp("2024-06-30"), "identity_quarantined": False},
    ])
    fake = FakeSession({
        "1111.jp": FakeResponse(good_csv()),
        "2222.jp": FakeResponse("Get your apikey: https://stooq.com/q/d/?get_apikey"),
        "3333.jp": FakeResponse("No data"),
    })
    secret = "SECRET_SHOULD_NEVER_APPEAR"
    result = s.probe_stooq(
        live_candidates,
        api_key=secret,
        history_start="2022-01-01",
        request_pause=0,
        session=fake,
    )
    status = dict(zip(result["code"], result["coverage_status"]))
    assert status["1111"] == "usable_near_delist"
    assert status["2222"] == "probe_error_auth"
    assert status["3333"] == "missing"
    assert secret not in "|".join(result["probe_error"].fillna("").astype(str))
    assert all(req.get("apikey") == secret for req in fake.requested)

    print("Stooq delisted-price coverage synthetic checks passed")


if __name__ == "__main__":
    main()
