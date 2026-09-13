# Prospective shadow evidence framework — 2026-09-13

Research-only infrastructure added in a parallel lane while the other chat continues V15 event×regime/quality-gate calibration. This work deliberately does not touch that modeling lane.

## Purpose

Retrospective 2025/2026 research is already exposed in multiple experiments, so a genuine promotion decision eventually needs post-freeze forward evidence. This framework records frozen-model candidate events append-only and resolves them later against the common next-session-open -> fifth-session-close endpoint.

## Guardrails

- candidate key includes experiment ID, model-freeze ID, symbol, signal date, and bin name;
- only `RAW_CAUSAL_INTRADAY` inputs are accepted;
- `POSTCLOSE_RECON_ONLY` and `DAILY_RESOLUTION_FALLBACK` are rejected;
- candidate append is idempotent and does not silently overwrite prior rows;
- unresolved or not-yet-matured 5BD endpoints remain explicitly pending/unresolved;
- no missing endpoint is imputed;
- no network retrieval, model tuning, production workflow change, Discord write, Sheet write, TradingView write, or daily-to-intraday synthesis occurs here.

## Verification

Synthetic tests passed **4/4**:

1. post-close reconstructed inputs fail closed;
2. duplicate candidate append is idempotent;
3. resolution uses the common next-official-session open to fifth-official-session close endpoint;
4. an immature candidate remains `PENDING_5BD`.

Files:
- `PROSPECTIVE_SHADOW_EVIDENCE_SPEC.json`
- `prospective_shadow.py`
- `test_prospective_shadow.py`

This is infrastructure only. It does not promote V12, V14, V15, Core, or Monster and does not alter any current production system.
