#!/usr/bin/env python3
"""Build the current JPX domestic-common snapshot without downloading Yahoo data.

TEST ONLY. This is a lightweight preflight used before expensive fixed-start
research so point-in-time membership parsing can fail fast.
"""
from __future__ import annotations

import bootstrap


def main() -> None:
    universe = bootstrap.dynamic_jpx_universe()
    if universe.empty:
        raise RuntimeError("JPX current universe snapshot is empty")
    print(f"jpx_current_snapshot_preflight: {len(universe)} symbols")


if __name__ == "__main__":
    main()
