"""Atomic Parquet writing and file-level manifests for research artifacts."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
from collections.abc import Mapping

import pandas as pd


FORBIDDEN_TOKENS = ("future", "target", "label", "realized", "forward_return")


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_decision_table(frame: pd.DataFrame) -> None:
    forbidden = [
        column for column in frame.columns
        if any(token in str(column).strip().lower() for token in FORBIDDEN_TOKENS)
    ]
    if forbidden:
        raise ValueError(f"outcome-like columns cannot be persisted in a decision table: {forbidden}")
    if frame.duplicated(["date", "symbol"]).any():
        raise ValueError("decision table contains duplicate symbol/date rows")


def write_parquet_artifact(
    frame: pd.DataFrame,
    path: str | Path,
    *,
    metadata: Mapping[str, object],
) -> dict[str, object]:
    """Persist a complete table and JSON receipt; never truncate or filter rows."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if "raw" in target.stem.lower() or "candidate_pool" in target.stem.lower():
        validate_decision_table(frame)
    with tempfile.NamedTemporaryFile(
        prefix=f".{target.name}.", suffix=".tmp", dir=target.parent, delete=False
    ) as temporary:
        temporary_path = Path(temporary.name)
    try:
        frame.to_parquet(temporary_path, engine="pyarrow", compression="zstd", index=False)
        os.replace(temporary_path, target)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise
    receipt = {
        "artifact": target.name,
        "format": "parquet",
        "rows": int(len(frame)),
        "columns": [str(column) for column in frame.columns],
        "sha256": sha256_file(target),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        **dict(metadata),
    }
    manifest_path = target.with_suffix(target.suffix + ".manifest.json")
    manifest_tmp = manifest_path.with_suffix(manifest_path.suffix + ".tmp")
    manifest_tmp.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(manifest_tmp, manifest_path)
    return receipt


def write_parquet_batches(
    batches,
    path: str | Path,
    *,
    metadata: Mapping[str, object],
) -> dict[str, object]:
    """Atomically write bounded-memory DataFrame batches to one Parquet artifact."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if "raw" in target.stem.lower() or "candidate_pool" in target.stem.lower():
        raise ValueError("streaming writer is for feature/artifact tables, not decision pools requiring global uniqueness checks")
    with tempfile.NamedTemporaryFile(
        prefix=f".{target.name}.", suffix=".tmp", dir=target.parent, delete=False
    ) as temporary:
        temporary_path = Path(temporary.name)
    writer = None
    rows = 0
    columns: list[str] | None = None
    schema = None
    try:
        writer = None
        for frame in batches:
            if frame.empty:
                continue
            table = pa.Table.from_pandas(frame, preserve_index=False)
            current_schema = table.schema.remove_metadata()
            if writer is None:
                schema = current_schema
                columns = [str(column) for column in frame.columns]
                writer = pq.ParquetWriter(temporary_path, table.schema, compression="zstd")
            elif not current_schema.equals(schema):
                raise ValueError("Parquet batch schema changed during streaming write")
            writer.write_table(table)
            rows += int(len(frame))
        if writer is None or rows == 0 or columns is None:
            raise ValueError("cannot write an empty Parquet batch stream")
        writer.close()
        writer = None
        os.replace(temporary_path, target)
    except Exception:
        if writer is not None:
            writer.close()
        temporary_path.unlink(missing_ok=True)
        raise
    receipt = {
        "artifact": target.name,
        "format": "parquet",
        "rows": rows,
        "columns": columns,
        "sha256": sha256_file(target),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "streamed_batches": True,
        **dict(metadata),
    }
    manifest_path = target.with_suffix(target.suffix + ".manifest.json")
    manifest_tmp = manifest_path.with_suffix(manifest_path.suffix + ".tmp")
    manifest_tmp.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(manifest_tmp, manifest_path)
    return receipt


def read_verified_parquet(path: str | Path) -> tuple[pd.DataFrame, dict[str, object]]:
    target = Path(path)
    manifest_path = target.with_suffix(target.suffix + ".manifest.json")
    receipt = json.loads(manifest_path.read_text(encoding="utf-8"))
    actual_hash = sha256_file(target)
    if actual_hash != receipt.get("sha256"):
        raise ValueError("Parquet artifact hash differs from its manifest")
    frame = pd.read_parquet(target, engine="pyarrow")
    if len(frame) != receipt.get("rows") or list(frame.columns) != receipt.get("columns"):
        raise ValueError("Parquet artifact schema or row count differs from its manifest")
    return frame, receipt


def read_verified_parquet_columns(
    path: str | Path,
    columns: list[str] | tuple[str, ...],
) -> tuple[pd.DataFrame, dict[str, object]]:
    """Verify a complete artifact hash while materializing only named columns."""
    requested = list(columns)
    if not requested or len(requested) != len(set(requested)):
        raise ValueError("projected Parquet columns must be non-empty and unique")
    target = Path(path)
    manifest_path = target.with_suffix(target.suffix + ".manifest.json")
    receipt = json.loads(manifest_path.read_text(encoding="utf-8"))
    if sha256_file(target) != receipt.get("sha256"):
        raise ValueError("Parquet artifact hash differs from its manifest")
    advertised = receipt.get("columns")
    if not isinstance(advertised, list) or not set(requested).issubset(advertised):
        raise ValueError("requested Parquet projection is absent from the verified schema")
    import pyarrow.parquet as pq

    table = pq.read_table(target, columns=requested)
    if table.num_rows != receipt.get("rows") or table.column_names != requested:
        raise ValueError("projected Parquet artifact row count or schema differs from its manifest")
    return table.to_pandas(), receipt
