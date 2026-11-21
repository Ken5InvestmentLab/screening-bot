"""Private, request-bound vendor evidence for an unfinished Cloud acquisition.

Pickles are local trusted run artifacts, never uploads or public assets. A
replay verifies its run context and every packet hash before deserializing;
missing/corrupt evidence never falls back to the network.
"""
from __future__ import annotations

import hashlib
import json
import os
import pickle
import tempfile
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from .network import transient_network_error


class RetainedResponseError(RuntimeError):
    pass


class RetainedProviderError(RetainedResponseError):
    """A verified archived provider exception rather than an archive mismatch."""


def _atomic(path: Path, content: bytes) -> None:
    descriptor, name = tempfile.mkstemp(prefix="." + path.name, suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class AcquisitionArchive:
    def __init__(self, directory: Path, context: dict, *, replay: bool = False):
        self.directory = directory.resolve()
        self.replay = replay
        self.sequence = 0
        self.manifest_path = self.directory / "manifest.json"
        self.context = json.loads(json.dumps(context, sort_keys=True))
        if replay:
            self.manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            if self.manifest.get("identity") != "CLOUD_ACQUISITION_V1" or self.manifest.get("context") != self.context:
                raise RetainedResponseError("Retained acquisition context differs (date/universe/period/previous SHA)")
        else:
            self.directory.mkdir(parents=True, exist_ok=False)
            self.manifest = {"identity": "CLOUD_ACQUISITION_V1", "context": self.context,
                             "createdAt": datetime.now(timezone.utc).isoformat(), "status": "acquiring", "requests": 0}
            self.mark("acquiring")

    def mark(self, status: str, **extra) -> None:
        if self.replay:
            return
        self.manifest.update(status=status, requests=self.sequence, **extra)
        _atomic(self.manifest_path, (json.dumps(self.manifest, ensure_ascii=False, indent=2) + "\n").encode())

    def request(self, request: dict, operation, errors: dict | Callable[[], dict]):
        # yfinance replaces shared._ERRORS during download. Resolve the live
        # dictionary after the call, rather than retaining its old reference.
        current_errors = errors if callable(errors) else lambda: errors
        self.sequence += 1
        request = json.loads(json.dumps(request, sort_keys=True))
        key = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()[:20]
        stem = self.directory / f"{self.sequence:05d}-{key}"
        packet, receipt = stem.with_suffix(".pkl"), stem.with_suffix(".json")
        if self.replay:
            if not receipt.exists():
                raise RetainedResponseError(f"Missing retained response {self.sequence}; network fallback is disabled")
            saved = json.loads(receipt.read_text(encoding="utf-8"))
            if saved.get("request") != request:
                raise RetainedResponseError("Retained response request mismatch")
            provider_errors = current_errors()
            provider_errors.clear()
            provider_errors.update(saved.get("providerErrors", {}))
            if saved.get("error"):
                if saved.get("transient") is True:
                    raise ConnectionError("Retained provider error: " + saved["error"])
                raise RetainedProviderError("Retained provider error: " + saved["error"])
            if not packet.exists() or _hash(packet) != saved.get("sha256"):
                raise RetainedResponseError("Retained response SHA-256 mismatch; network fallback is disabled")
            with packet.open("rb") as stream:
                return pickle.load(stream)
        try:
            value = operation()
        except Exception as error:
            _atomic(receipt, json.dumps({"request": request, "error": f"{type(error).__name__}: {error}",
                                       "transient": transient_network_error(error),
                                       "providerErrors": {str(k): str(v) for k, v in current_errors().items()}}).encode())
            self.mark("acquiring")
            raise
        descriptor, name = tempfile.mkstemp(prefix=".response-", suffix=".tmp", dir=self.directory)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                pickle.dump(value, stream, protocol=pickle.HIGHEST_PROTOCOL)
            os.replace(name, packet)
        finally:
            Path(name).unlink(missing_ok=True)
        _atomic(receipt, json.dumps({"request": request, "sha256": _hash(packet),
                                   "providerErrors": {str(k): str(v) for k, v in current_errors().items()}}).encode())
        self.mark("acquiring")
        return value

    def info(self) -> dict:
        return {"directory": str(self.directory), "manifestSha256": _hash(self.manifest_path),
                "requests": self.sequence, "replayed": self.replay}

    def verified_revision_info(self) -> dict:
        """Bind a revision decision to every retained request receipt + packet.

        Read-only streaming verification; never deserializes or reissues a request.
        """
        inventory = []
        for sequence in range(1, self.sequence + 1):
            found = list(self.directory.glob(f"{sequence:05d}-*.json"))
            if len(found) != 1:
                raise RetainedResponseError("revision evidence receipt missing/ambiguous")
            receipt = found[0]
            raw = receipt.read_bytes()
            saved = json.loads(raw.decode("utf-8"))
            request = saved.get("request")
            key = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()[:20]
            if receipt.stem != f"{sequence:05d}-{key}":
                raise RetainedResponseError("revision evidence request identity mismatch")
            packet_sha = None
            if not saved.get("error"):
                packet = receipt.with_suffix(".pkl")
                if not packet.exists() or _hash(packet) != saved.get("sha256"):
                    raise RetainedResponseError("revision evidence packet SHA mismatch")
                packet_sha = saved["sha256"]
            inventory.append({"receipt": receipt.name, "receiptSha256": hashlib.sha256(raw).hexdigest(), "packetSha256": packet_sha})
        if not inventory:
            raise RetainedResponseError("revision evidence has no retained requests")
        return {**self.info(), "responseInventorySha256": hashlib.sha256(json.dumps(inventory, sort_keys=True, separators=(",", ":")).encode()).hexdigest(), "responseInventory": inventory}
