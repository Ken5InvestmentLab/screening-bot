"""Publish the shared display generated from the owner reference renderers."""
import hashlib
import json
from pathlib import Path
import subprocess

from .files import file_sha, read
from .member_publisher import (
    _INSERT_MANIFEST, _INSERT_PART, _MANIFEST, _batches, _identity,
)


SCHEMA = "NEW_A_MEMBER_REFERENCE_V1"
READY_INDEX = 10_000
MAX_VARIANT_BYTES = 512 * 1024
MAX_INDEX_BYTES = 1024 * 1024
HISTORY_INDEX = 'history.index'
MAX_PART_BYTES = 48 * 1024
CHUNK_CHARACTERS = 12_000
VARIANTS = {
    f"{page}.{preset}"
    for page in ("dashboard", "analytics")
    for preset in ("defensive", "medium", "return_priority")
}


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def encode(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def describe(text):
    content = text.encode()
    return {"bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}


def validated_display(value, source):
    require(set(value) == {"source", "variants"} and value["source"] == source
            and isinstance(value["variants"], dict), "shared reference display source differs")
    items = set(value["variants"])
    history_pages = len(items - VARIANTS - {HISTORY_INDEX})
    expected = VARIANTS | {f"history.{page}" for page in range(1, history_pages + 1)} | (items & {HISTORY_INDEX})
    require(history_pages <= 200 and items == expected, "shared reference display inventory differs")
    parts = []
    variants = []
    for item, markup in sorted(value["variants"].items()):
        require(isinstance(markup, str) and markup, "invalid reference display")
        if item == HISTORY_INDEX:
            index = json.loads(markup)
            require(set(index) == {"names", "rows"} and isinstance(index["names"], list)
                    and isinstance(index["rows"], list) and len(index["rows"]) <= 100 * history_pages,
                    "reference history index differs")
        elif item.startswith("history."):
            history = json.loads(markup)
            require(set(history) == {"page", "rows"} and history["page"] == int(item.split(".")[1])
                    and isinstance(history["rows"], list) and len(history["rows"]) <= 100
                    and (bool(history["rows"]) or history_pages == history["page"] == 1),
                    "reference history and page inventory differ")
        else:
            require(markup.startswith("<"), "invalid reference display markup")
        descriptor = describe(markup)
        limit = MAX_INDEX_BYTES if item == HISTORY_INDEX else MAX_VARIANT_BYTES
        require(descriptor["bytes"] <= limit, "shared reference display exceeds its byte limit")
        chunks = []
        for offset in range(0, len(markup), CHUNK_CHARACTERS):
            text = encode({"markup": markup[offset:offset + CHUNK_CHARACTERS]})
            part = describe(text)
            require(part["bytes"] <= MAX_PART_BYTES, "shared reference display part exceeds its byte limit")
            chunks.append({"index": len(parts), **part})
            parts.append(text)
        require(len(chunks) <= 96, "reference display requires too many parts")
        variants.append({"item": item, **descriptor, "parts": chunks})
    manifest = encode({"schema": SCHEMA, "source": source, "variants": variants})
    require(describe(manifest)["bytes"] <= 64 * 1024, "shared reference manifest exceeds its byte limit")
    return manifest, parts


def import_member_reference(database, value, source, read_official_ready):
    identity = _identity(source) + "\n" + SCHEMA
    manifest, parts = validated_display(value, source)
    signature = describe(manifest)["sha256"]
    marker = encode({"digest": signature})
    require(read_official_ready() == source, "owner generation changed before reference stage")
    found = database.query(_MANIFEST, (identity,))
    if not found:
        database.query(_INSERT_MANIFEST, (identity, signature, manifest))
        found = database.query(_MANIFEST, (identity,))
    require(found == [{"digest": signature, "json": manifest}], "shared reference manifest readback differs")
    select = "SELECT idx,json FROM private_projection_part WHERE identity=? AND kind='analytics'"
    current = database.query(select + " AND idx=?", (identity, READY_INDEX))
    require(current in ([], [{"idx": READY_INDEX, "json": marker}]), "reference ready marker differs")
    if not current:
        existing = {row["idx"] for row in database.query(
            "SELECT idx FROM private_projection_part WHERE identity=? AND kind='analytics'", (identity,))}
        require(existing.issubset(range(len(parts))), "unrecognized reference part exists")
        additions = [(_INSERT_PART, (identity, "analytics", index, part))
                     for index, part in enumerate(parts) if index not in existing]
        for batch in _batches(additions):
            database.batch(batch)
    total = database.query(
        "SELECT COUNT(*) AS total FROM private_projection_part WHERE identity=? AND kind='analytics' AND idx<>?",
        (identity, READY_INDEX),
    )
    require(total == [{"total": len(parts)}], "shared reference part inventory differs")
    for group in _batches(list(enumerate(parts))):
        expected = [{"idx": index, "json": part} for index, part in group]
        rows = database.query(select + " AND idx BETWEEN ? AND ? ORDER BY idx",
                              (identity, group[0][0], group[-1][0]))
        require(rows == expected, "shared reference part readback differs")
    require(read_official_ready() == source, "owner generation changed before reference selection")
    if not current:
        database.query(_INSERT_PART, (identity, "analytics", READY_INDEX, marker))
    require(database.query(select + " AND idx=?", (identity, READY_INDEX))
            == [{"idx": READY_INDEX, "json": marker}] and read_official_ready() == source,
            "reference view activation was not confirmed")
    return {"source": source, "manifest_sha256": signature, "parts": len(parts)}


def build_member_reference(repo, node, bundle, ready_proof, directory):
    builder = repo / "weak-early-beta-gate/scripts/prepare-new-a-reference-view.cjs"
    completed = subprocess.run(
        [node, str(builder), "--bundle", str(bundle), "--ready-proof", str(ready_proof),
         "--ready-proof-sha256", file_sha(ready_proof), "--out", str(directory)],
        cwd=repo, capture_output=True, timeout=240,
    )
    require(completed.returncode == 0, "owner reference projection build failed")
    result = directory / "reference-view.json"
    require(result.resolve(strict=True) == result and result.stat().st_size < 16 * 1024 * 1024,
            "owner reference projection exceeds its file limit")
    return read(result)
