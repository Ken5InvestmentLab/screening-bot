from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

ANCHOR_DATE = pd.Timestamp("2026-09-11")
WINDOW_START = pd.Timestamp("2024-10-01")
WINDOW_END = pd.Timestamp("2025-12-30")
FETCH_START = "2024-05-01"
FETCH_END_EXCLUSIVE = "2026-01-20"
BATCH = 40
MIN_RESTORED_DAILY_COVERAGE = 1.00


def clean_symbol(x: object) -> str:
    s = str(x).strip()
    if s.endswith(".0"):
        s = s[:-2]
    return s


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def members_as_of(
    current_codes: set[str],
    events: pd.DataFrame,
    as_of: pd.Timestamp,
) -> set[str]:
    if as_of > ANCHOR_DATE:
        raise ValueError("as_of after anchor")
    members = set(current_codes)
    z = events[
        (events["event_date"] > as_of)
        & (events["event_date"] <= ANCHOR_DATE)
    ]
    for row in z.sort_values(
        ["event_date", "code"],
        ascending=[False, True],
        kind="mergesort",
    ).itertuples(index=False):
        code = clean_symbol(row.code)
        if row.event == "listing":
            members.discard(code)
        elif row.event == "delisting":
            members.add(code)
        else:
            raise RuntimeError(f"unknown event type {row.event}")
    return members


def membership_intervals(
    current_codes: set[str],
    events: pd.DataFrame,
    dates: list[pd.Timestamp],
) -> dict[str, set[str]]:
    return {
        d.strftime("%Y-%m-%d"): members_as_of(current_codes, events, d)
        for d in dates
    }


def split_factor(
    split_map: dict[str, list[tuple[pd.Timestamp, float]]],
    symbol: str,
    date: pd.Timestamp,
) -> float:
    f = 1.0
    for event_date, ratio in split_map.get(symbol, []):
        if event_date > date:
            f *= ratio
    return float(f)


def _epoch(date_s: str) -> int:
    return int(pd.Timestamp(date_s, tz="UTC").timestamp())


def _split_ratio_from_event(ev: dict) -> float | None:
    try:
        num = float(ev.get("numerator"))
        den = float(ev.get("denominator"))
        if num > 0 and den > 0:
            return num / den
    except Exception:
        pass
    text = str(ev.get("splitRatio") or "").strip()
    if ":" in text:
        try:
            a, b = text.split(":", 1)
            a = float(a)
            b = float(b)
            if a > 0 and b > 0:
                return a / b
        except Exception:
            pass
    return None


def fetch_restored_one(code: str) -> tuple[pd.DataFrame, list[dict], str | None]:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{code}.T"
    last = None
    for attempt in range(5):
        try:
            r = requests.get(
                url,
                params={
                    "period1": _epoch(FETCH_START),
                    "period2": _epoch(FETCH_END_EXCLUSIVE),
                    "interval": "1d",
                    "events": "div,splits",
                    "includePrePost": "false",
                },
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (X11; Linux x86_64) "
                        "AppleWebKit/537.36 Chrome/140 Safari/537.36"
                    ),
                    "Accept": "application/json,text/plain,*/*",
                },
                timeout=30,
            )
            if r.status_code in {400, 404, 410, 422}:
                return pd.DataFrame(), [], f"http_{r.status_code}_terminal"
            if r.status_code in {429, 502, 503, 504}:
                last = f"http_{r.status_code}"
                time.sleep(1.0 * (attempt + 1))
                continue
            r.raise_for_status()
            payload = r.json()
            err = payload.get("chart", {}).get("error")
            if err:
                return pd.DataFrame(), [], (
                    err.get("description") or "chart_error"
                )
            result = (payload.get("chart", {}).get("result") or [None])[0]
            if not result:
                return pd.DataFrame(), [], "no_result"
            q = result.get("indicators", {}).get("quote", [{}])[0]
            ts = result.get("timestamp") or []
            keys = ["open", "high", "low", "close", "volume"]
            n = min([len(ts)] + [len(q.get(k) or []) for k in keys])
            rows = []
            for i in range(n):
                vals = [q.get(k, [None] * n)[i] for k in keys]
                if any(v is None for v in vals):
                    continue
                o, h, lo, cl, vol = map(float, vals)
                if cl <= 0 or h <= 0 or lo <= 0 or h < lo or vol < 0:
                    continue
                dt = (
                    pd.to_datetime(int(ts[i]), unit="s", utc=True)
                    .tz_convert("Asia/Tokyo")
                    .tz_localize(None)
                    .normalize()
                )
                rows.append({
                    "date": dt,
                    "open": o,
                    "high": h,
                    "low": lo,
                    "close": cl,
                    "volume": vol,
                    "symbol": code,
                })

            split_rows = []
            for ev in (result.get("events", {}).get("splits") or {}).values():
                ratio = _split_ratio_from_event(ev)
                if ratio is None:
                    continue
                dt = (
                    pd.to_datetime(int(ev["date"]), unit="s", utc=True)
                    .tz_convert("Asia/Tokyo")
                    .tz_localize(None)
                    .normalize()
                )
                split_rows.append({
                    "symbol": code,
                    "event_date": dt,
                    "split_ratio": float(ratio),
                })

            fr = pd.DataFrame(rows)
            if fr.empty:
                return fr, split_rows, "no_daily_rows"
            return fr, split_rows, None
        except Exception as exc:
            last = f"{type(exc).__name__}: {exc}"
            time.sleep(0.8 * (attempt + 1))
    return pd.DataFrame(), [], last or "fetch_failed"


def batched_download_restored(
    symbols: list[str],
    batch: int,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    # Delisted symbols are fetched independently. A single invalid/delisted
    # ticker must never blank an entire multi-ticker request.
    daily_frames: list[pd.DataFrame] = []
    split_rows: list[dict] = []
    requested = set(symbols)
    usable: set[str] = set()
    failures: list[dict] = []

    for i, code in enumerate(sorted(symbols), 1):
        fr, sp, err = fetch_restored_one(code)
        if not fr.empty:
            daily_frames.append(fr)
            usable.add(code)
        if sp:
            split_rows.extend(sp)
        if err is not None:
            failures.append({"symbol": code, "error": err})
        if i % 25 == 0:
            print(
                f"restored direct daily {i}/{len(symbols)} "
                f"usable={len(usable)}",
                flush=True,
            )
        time.sleep(0.03)

    daily = (
        pd.concat(daily_frames, ignore_index=True)
        if daily_frames
        else pd.DataFrame(
            columns=[
                "date", "open", "high", "low",
                "close", "volume", "symbol",
            ]
        )
    )
    splits = pd.DataFrame(
        split_rows,
        columns=["symbol", "event_date", "split_ratio"],
    )
    if not splits.empty:
        splits["symbol"] = splits["symbol"].map(clean_symbol)
        splits["event_date"] = pd.to_datetime(splits["event_date"])
        splits["split_ratio"] = pd.to_numeric(
            splits["split_ratio"], errors="coerce"
        )
        splits = (
            splits.dropna()
            .drop_duplicates(["symbol", "event_date", "split_ratio"])
            .sort_values(["symbol", "event_date"])
            .reset_index(drop=True)
        )

    receipt = {
        "requested_restored_symbols": len(requested),
        "usable_restored_symbols": len(usable),
        "coverage_fraction": (
            float(len(usable) / len(requested)) if requested else 1.0
        ),
        "missing_symbols": sorted(requested - usable),
        "failures": failures,
        "restored_split_events": int(len(splits)),
        "fetch_mode": "individual Yahoo chart API daily requests",
    }
    return daily, splits, receipt


def load_frozen_daily(path: Path) -> pd.DataFrame:
    d = pd.read_csv(
        path,
        usecols=["date", "open", "high", "low", "close", "volume", "symbol"],
        dtype={"symbol": str},
        low_memory=False,
    )
    d["date"] = pd.to_datetime(d["date"], errors="coerce").dt.normalize()
    d["symbol"] = d["symbol"].map(clean_symbol)
    for c in ["open", "high", "low", "close", "volume"]:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    return (
        d.dropna(subset=["date", "symbol", "close", "volume"])
        .sort_values(["symbol", "date"])
        .drop_duplicates(["symbol", "date"], keep="last")
        .reset_index(drop=True)
    )


def load_events(path: Path) -> pd.DataFrame:
    e = pd.read_csv(path, dtype={"code": str})
    e["event_date"] = pd.to_datetime(e["event_date"]).dt.normalize()
    e["code"] = e["code"].map(clean_symbol)
    return e


def load_splits(path: Path) -> pd.DataFrame:
    s = pd.read_csv(path, dtype={"symbol": str})
    s["event_date"] = pd.to_datetime(s["event_date"]).dt.normalize()
    s["symbol"] = s["symbol"].map(clean_symbol)
    s["split_ratio"] = pd.to_numeric(s["split_ratio"], errors="coerce")
    if ((s["split_ratio"] <= 0) | ~np.isfinite(s["split_ratio"])).any():
        raise RuntimeError("invalid accepted V46 split ratio")
    return s


def build_split_map(splits: pd.DataFrame) -> dict[str, list[tuple[pd.Timestamp, float]]]:
    out: dict[str, list[tuple[pd.Timestamp, float]]] = {}
    for sym, g in splits.groupby("symbol", sort=False):
        out[str(sym)] = [
            (pd.Timestamp(r.event_date), float(r.split_ratio))
            for r in g.sort_values("event_date").itertuples(index=False)
        ]
    return out



def add_identity_epoch(
    daily: pd.DataFrame,
    events: pd.DataFrame,
) -> pd.DataFrame:
    """Reset historical continuity at every official listing event for a code.

    Yahoo may stitch predecessor/reused-code history under a later code.
    Epoch 0 is history before the first captured listing event; every listing
    increments the epoch. Lagged eligibility fields must never cross epochs.
    """
    x = daily.copy()
    listing_map: dict[str, list[pd.Timestamp]] = {}
    q = events[events["event"] == "listing"].copy()
    for code, g in q.groupby("code", sort=False):
        listing_map[clean_symbol(code)] = sorted(
            pd.Timestamp(v).normalize() for v in g["event_date"].tolist()
        )

    epochs = []
    starts = []
    for row in x[["symbol", "date"]].itertuples(index=False):
        dates = listing_map.get(str(row.symbol), [])
        prior = [dt for dt in dates if dt <= pd.Timestamp(row.date)]
        epochs.append(len(prior))
        starts.append(prior[-1] if prior else pd.NaT)
    x["identity_epoch"] = epochs
    x["identity_start"] = starts
    return x


def materialize_daily_candidates(
    daily: pd.DataFrame,
    memberships: dict[str, set[str]],
    split_map: dict[str, list[tuple[pd.Timestamp, float]]],
    events: pd.DataFrame,
) -> tuple[pd.DataFrame, dict]:
    d = add_identity_epoch(daily, events)
    d = d.sort_values(["symbol", "identity_epoch", "date"]).copy()
    g = d.groupby(["symbol", "identity_epoch"], sort=False)
    d["prev_date"] = g["date"].shift(1)
    d["prev_close_adjusted"] = g["close"].shift(1)
    d["prev_volume"] = g["volume"].shift(1)

    q = d[d["date"].between(WINDOW_START, WINDOW_END)].copy()
    q["date_s"] = q["date"].dt.strftime("%Y-%m-%d")
    q["pit_member"] = [
        str(sym) in memberships.get(dt, set())
        for sym, dt in zip(q["symbol"], q["date_s"])
    ]

    factors = []
    for row in q[["symbol", "prev_date"]].itertuples(index=False):
        if pd.isna(row.prev_date):
            factors.append(np.nan)
        else:
            factors.append(
                split_factor(
                    split_map,
                    str(row.symbol),
                    pd.Timestamp(row.prev_date),
                )
            )
    q["future_split_factor_from_prev_date"] = factors
    q["prev_close_pit"] = (
        q["prev_close_adjusted"]
        * q["future_split_factor_from_prev_date"]
    )

    base = (
        q["pit_member"]
        & (q["prev_volume"] >= 10000)
        & q["prev_close_pit"].notna()
    )
    q["eligible_nocap_daily"] = base
    q["eligible_cap1000_daily"] = base & (q["prev_close_pit"] <= 1000)

    cols = [
        "date_s", "symbol", "prev_date", "prev_close_adjusted",
        "prev_close_pit", "prev_volume",
        "future_split_factor_from_prev_date",
        "eligible_nocap_daily", "eligible_cap1000_daily",
    ]
    out = q.loc[
        q["eligible_nocap_daily"] | q["eligible_cap1000_daily"],
        cols,
    ].copy()

    def arm_stats(col: str) -> dict:
        z = q[q[col]]
        return {
            "symbol_date_rows": int(len(z)),
            "unique_symbols": int(z["symbol"].nunique()),
            "unique_dates": int(z["date_s"].nunique()),
            "median_symbols_per_date": (
                float(z.groupby("date_s")["symbol"].nunique().median())
                if len(z) else 0.0
            ),
            "max_symbols_per_date": (
                int(z.groupby("date_s")["symbol"].nunique().max())
                if len(z) else 0
            ),
        }

    return out, {
        "NOCAP": arm_stats("eligible_nocap_daily"),
        "CAP1000_PIT": arm_stats("eligible_cap1000_daily"),
    }


def synthetic_checks() -> None:
    current = {"1000"}
    events = pd.DataFrame([
        {
            "event_date": pd.Timestamp("2025-02-01"),
            "code": "2000",
            "event": "delisting",
        },
        {
            "event_date": pd.Timestamp("2025-06-01"),
            "code": "3000",
            "event": "listing",
        },
    ])
    m = members_as_of(current, events, pd.Timestamp("2025-01-15"))
    assert m == {"1000", "2000"}
    m2 = members_as_of(current, events, pd.Timestamp("2025-07-01"))
    assert m2 == {"1000"}

    sm = {"X": [(pd.Timestamp("2025-04-01"), 10.0)]}
    assert math.isclose(split_factor(sm, "X", pd.Timestamp("2025-03-31")), 10.0)
    assert math.isclose(split_factor(sm, "X", pd.Timestamp("2025-04-01")), 1.0)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--frozen-daily", required=True, type=Path)
    ap.add_argument("--membership-events", required=True, type=Path)
    ap.add_argument("--v46-splits", required=True, type=Path)
    ap.add_argument("--output-dir", required=True, type=Path)
    ap.add_argument("--batch", type=int, default=BATCH)
    a = ap.parse_args()

    synthetic_checks()
    frozen = load_frozen_daily(a.frozen_daily)
    current_codes = set(frozen["symbol"].unique())
    if len(current_codes) != 3700:
        raise RuntimeError(
            f"unexpected frozen current universe {len(current_codes)} != 3700"
        )

    events = load_events(a.membership_events)
    signal_dates = sorted(
        pd.Timestamp(x)
        for x in frozen.loc[
            frozen["date"].between(WINDOW_START, WINDOW_END),
            "date",
        ].unique()
    )
    memberships = membership_intervals(current_codes, events, signal_dates)
    pit_union = set().union(*memberships.values()) if memberships else set()
    restored = sorted(pit_union - current_codes)

    restored_daily, restored_splits, restored_receipt = batched_download_restored(
        restored,
        a.batch,
    )

    merged_daily = pd.concat(
        [frozen, restored_daily],
        ignore_index=True,
        sort=False,
    )
    merged_daily = (
        merged_daily.sort_values(["symbol", "date"])
        .drop_duplicates(["symbol", "date"], keep="last")
        .reset_index(drop=True)
    )

    v46_splits = load_splits(a.v46_splits)
    all_splits = pd.concat(
        [v46_splits, restored_splits],
        ignore_index=True,
        sort=False,
    )
    if len(all_splits):
        all_splits = (
            all_splits.drop_duplicates(
                ["symbol", "event_date", "split_ratio"],
                keep="last",
            )
            .sort_values(["symbol", "event_date"])
            .reset_index(drop=True)
        )
    split_map = build_split_map(all_splits)

    candidates, arm_stats = materialize_daily_candidates(
        merged_daily,
        memberships,
        split_map,
        events,
    )

    required_nocap = sorted(
        candidates.loc[candidates["eligible_nocap_daily"], "symbol"].unique()
    )
    required_cap = sorted(
        candidates.loc[candidates["eligible_cap1000_daily"], "symbol"].unique()
    )
    missing_restored = set(restored_receipt["missing_symbols"])
    required_missing_nocap = sorted(set(required_nocap) & missing_restored)
    required_missing_cap = sorted(set(required_cap) & missing_restored)

    out = a.output_dir
    out.mkdir(parents=True, exist_ok=True)
    candidates.to_csv(out / "v47_daily_candidate_symbol_dates.csv", index=False)
    all_splits.to_csv(out / "v47_all_split_events.csv", index=False)
    restored_daily.to_csv(out / "v47_restored_daily.csv", index=False)
    (out / "v47_required_intraday_nocap.txt").write_text(
        "\n".join(required_nocap) + "\n",
        encoding="utf-8",
    )
    (out / "v47_required_intraday_cap1000.txt").write_text(
        "\n".join(required_cap) + "\n",
        encoding="utf-8",
    )

    report = {
        "scope": "outcome-blind V47 daily/PIT materialization",
        "window": [
            WINDOW_START.strftime("%Y-%m-%d"),
            WINDOW_END.strftime("%Y-%m-%d"),
        ],
        "current_frozen_symbols": len(current_codes),
        "pit_union_symbols": len(pit_union),
        "restored_delisted_union_symbols": len(restored),
        "restored_daily_fetch": restored_receipt,
        "arms": arm_stats,
        "required_intraday": {
            "NOCAP": {
                "unique_symbols": len(required_nocap),
                "required_missing_restored_symbols": required_missing_nocap,
            },
            "CAP1000_PIT": {
                "unique_symbols": len(required_cap),
                "required_missing_restored_symbols": required_missing_cap,
            },
        },
        "daily_coverage_pass": bool(
            restored_receipt["coverage_fraction"] >= MIN_RESTORED_DAILY_COVERAGE
        ),
        "daily_coverage_min": MIN_RESTORED_DAILY_COVERAGE,
        "strategy_returns_opened": False,
        "model_scores_opened": False,
        "production_writes": False,
        "next_action": (
            "If daily_coverage_pass=true, shard-fetch intraday only for "
            "v47_required_intraday_nocap.txt (superset of CAP1000), then issue "
            "an intraday coverage receipt before any strategy scoring. If false, "
            "repair missing restored/delisted daily histories before continuing; "
            "do not silently drop missing names."
        ),
    }

    report_path = out / "v47_daily_materialization_receipt.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    hashes = {
        p.name: sha256_file(p)
        for p in [
            out / "v47_daily_candidate_symbol_dates.csv",
            out / "v47_all_split_events.csv",
            out / "v47_restored_daily.csv",
            out / "v47_required_intraday_nocap.txt",
            out / "v47_required_intraday_cap1000.txt",
            report_path,
        ]
    }
    (out / "v47_daily_materialization_hashes.json").write_text(
        json.dumps(hashes, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
