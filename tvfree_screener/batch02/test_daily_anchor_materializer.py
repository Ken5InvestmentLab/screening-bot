from datetime import datetime
from zoneinfo import ZoneInfo

from tvfree_screener.batch02.daily_anchor_materializer import materialize_session

JST = ZoneInfo("Asia/Tokyo")


def rows(missing=None, volume=100.0):
    out = []
    for h in range(9, 16):
        if h == missing:
            continue
        base = 100 + h - 9
        out.append({
            "timestamp": datetime(2026, 9, 1, h, 0, tzinfo=JST).isoformat(),
            "symbol": "9999",
            "open": base,
            "high": base + 2,
            "low": base - 1,
            "close": base + 1,
            "volume": volume,
        })
    return out


def daily(volume=1000.0):
    return {
        "date": "2026-09-01",
        "symbol": "9999",
        "open": 100.0,
        "high": 108.0,
        "low": 99.0,
        "close": 107.0,
        "volume": volume,
    }


def test_complete_session_materializes_without_mutating_raw():
    raw = rows()
    raw_before = [dict(x) for x in raw]
    result = materialize_session(
        raw,
        daily(volume=1050.0),
        feature_cutoff_jst=datetime(2026, 9, 1, 13, 0, tzinfo=JST),
        daily_final_available_at_jst=datetime(2026, 9, 1, 16, 0, tzinfo=JST),
    )
    assert raw == raw_before
    assert len(result.rows) == 7
    assert result.reconstruction_tier == "A_FULL_RECON_POSTCLOSE"
    assert result.causal_signal_eligibility == "POSTCLOSE_RECON_ONLY"
    assert result.scale_applied is True
    assert result.volume_reconciled is True
    assert result.rows[0]["open"] == 100.0
    assert result.rows[-1]["close"] == 107.0
    assert max(r["high"] for r in result.rows) == 108.0
    assert min(r["low"] for r in result.rows) == 99.0
    assert abs(sum(r["volume"] for r in result.rows) - 1050.0) < 1e-9


def test_missing_slot_produces_one_daily_row_not_fake_am_pm():
    result = materialize_session(rows(missing=12), daily())
    assert result.reconstruction_tier == "C_DAILY_RESOLUTION_FALLBACK"
    assert len(result.rows) == 1
    assert result.rows[0]["resolution"] == "1D"
    assert "bin_name" not in result.rows[0]


def test_inconsistent_ohlc_scale_falls_back():
    d = daily()
    d["high"] = 150.0
    result = materialize_session(rows(), d)
    assert result.reconstruction_tier == "C_DAILY_RESOLUTION_FALLBACK"
    assert result.scale_applied is False
    assert len(result.rows) == 1


def test_untrusted_volume_keeps_price_recon_but_does_not_scale_volume():
    result = materialize_session(rows(), daily(volume=3000.0))
    assert result.reconstruction_tier == "B_PRICE_RECON_POSTCLOSE"
    assert result.volume_reconciled is False
    assert sum(r["volume"] for r in result.rows) == 700.0


def test_postclose_use_requires_explicit_daily_availability():
    result = materialize_session(
        rows(),
        daily(volume=1050.0),
        feature_cutoff_jst=datetime(2026, 9, 1, 16, 5, tzinfo=JST),
        daily_final_available_at_jst=datetime(2026, 9, 1, 16, 0, tzinfo=JST),
    )
    assert result.causal_signal_eligibility == "POSTCLOSE_CAUSAL_OK"


def test_invalid_daily_and_incomplete_hourly_is_unusable():
    result = materialize_session(rows(missing=10), None)
    assert result.reconstruction_tier == "D_UNUSABLE"
    assert result.rows == ()
