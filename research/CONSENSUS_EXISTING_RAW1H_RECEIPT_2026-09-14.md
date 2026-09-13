# Consensus raw Yahoo 1H preservation opportunity — 2026-09-14

Research-only cross-lane provenance note. No new Yahoo fetch is started.

## Existing frozen-ish raw source from Core lane

The Core lane's canonical endpoint artifact records its source 1H fetch run as:

- source fetch run: **34592896202**
- raw requested span: 2024-09-16..2026-09-10
- target set: 1,332 symbols (narrower than V43/V44's 1,910-symbol requested set)

Eight raw shard artifacts from that run still exist:

| shard | artifact id | digest | expires |
|---|---:|---|---|
| 0 | 10196449529 | sha256:9421fc93cc39c875a45dad09eb199e991e856f89b407cdf50e2a365fd529a137 | 2026-09-25 |
| 1 | 10196417793 | sha256:20ae841c47304d0c7f27ab9a42ccd23a499375dd1676e797dc70b5ababe41a56 | 2026-09-25 |
| 2 | 10196390666 | sha256:a221b36de3153dd256a977861166239ce19c829890cc085aa37cc33e39f771db | 2026-09-25 |
| 3 | 10196390156 | sha256:141ce33f9c4f678dbd1a6800e33ead97e0c7e0fa8654b78adc5f7cd0e357fa72 | 2026-09-25 |
| 4 | 10196451479 | sha256:dc48120319252a460009213e36faf286815869f91162a492bc75dedc89e62c34 | 2026-09-25 |
| 5 | 10196398807 | sha256:c476912bd559cdf310cdbf1e5b18ad7ed68950aa1b3bd21819398449f6638c54 | 2026-09-25 |
| 6 | 10196399262 | sha256:459f4303e7b6d873fd6e1c67a32a71e6b39d39982dc4e256b177d9d5f8ed428c | 2026-09-25 |
| 7 | 10196438873 | sha256:3123938c92c1b16d0ac2b34ea6776cb949283e1fe9a692b54843cd8315d84f2d | 2026-09-25 |

## Boundary

This panel cannot silently replace the V43/V44 research input because:
- it covers 1,332 target symbols, not the V43/V44 requested 1,910;
- using it as the full universe would change the cross-sectional ranks and market context.

It *can* be used for:
- raw-bar reproducibility spot checks on overlapping symbols;
- reconstructing exact input history for a subset if Yahoo later truncates;
- diagnosing provider drift without launching a new fetch.

The Consensus lane will not refetch or claim ownership of the Core data pipeline.
