from __future__ import annotations

import pandas as pd

from normalize_core24_raw1h_for_v47 import normalize_frame


def main() -> None:
    raw = pd.DataFrame(
        [
            {
                "timestamp": "2025-05-30 09:00:00+0900",
                "symbol": "1000",
                "open": 100.0,
                "high": 110.0,
                "low": 90.0,
                "close": 105.0,
                "volume": 1000.0,
            },
            {
                "timestamp": "2025-06-02 09:00:00+0900",
                "symbol": "1000",
                "open": 52.0,
                "high": 55.0,
                "low": 50.0,
                "close": 54.0,
                "volume": 2000.0,
            },
            {
                "timestamp": "2025-05-30 13:00:00+0900",
                "symbol": "2000",
                "open": 300.0,
                "high": 310.0,
                "low": 295.0,
                "close": 305.0,
                "volume": 900.0,
            },
        ]
    )
    split_map = {"1000": [("2025-06-01", 2.0)]}
    out = normalize_frame(raw, split_map)

    pre = out.iloc[0]
    assert pre["open"] == 50.0
    assert pre["high"] == 55.0
    assert pre["low"] == 45.0
    assert pre["close"] == 52.5
    assert pre["volume"] == 1000.0
    assert pre["core24_future_split_factor"] == 2.0
    assert bool(pre["core24_price_basis_normalized"]) is True
    assert pre["close"] * pre["core24_future_split_factor"] == 105.0

    post = out.iloc[1]
    assert post["close"] == 54.0
    assert post["volume"] == 2000.0
    assert post["core24_future_split_factor"] == 1.0
    assert bool(post["core24_price_basis_normalized"]) is False

    no_split = out.iloc[2]
    assert no_split["close"] == 305.0
    assert no_split["volume"] == 900.0
    assert no_split["core24_future_split_factor"] == 1.0

    print("core24 -> V47 raw price-basis normalization contract: PASS")


if __name__ == "__main__":
    main()
