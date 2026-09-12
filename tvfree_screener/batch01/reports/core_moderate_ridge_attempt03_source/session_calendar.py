"""Frozen, hash-checked Tokyo Stock Exchange session calendar."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
from collections.abc import Sequence

import pandas as pd


@dataclass(frozen=True)
class SessionCalendar:
    sessions: pd.DatetimeIndex
    sha256: str
    source: str

    def __post_init__(self) -> None:
        normalized = pd.DatetimeIndex(pd.to_datetime(self.sessions, errors="raise")).normalize()
        if normalized.empty:
            raise ValueError("session calendar is empty")
        if normalized.has_duplicates or not normalized.is_monotonic_increasing:
            raise ValueError("session calendar must be unique and strictly increasing")
        object.__setattr__(self, "sessions", normalized)

    @classmethod
    def from_csv(cls, path: str | Path, *, expected_sha256: str | None = None) -> "SessionCalendar":
        source_path = Path(path)
        digest = hashlib.sha256(source_path.read_bytes()).hexdigest()
        if expected_sha256 is not None and digest != expected_sha256:
            raise ValueError("session calendar hash does not match its frozen manifest")
        frame = pd.read_csv(source_path, dtype={"date": "string"})
        if list(frame.columns) != ["date", "session_index"]:
            raise ValueError("calendar CSV must contain date,session_index")
        if frame["date"].isna().any() or frame["session_index"].isna().any():
            raise ValueError("calendar CSV contains missing values")
        indexes = pd.to_numeric(frame["session_index"], errors="raise").astype("int64")
        if indexes.tolist() != list(range(len(frame))):
            raise ValueError("session_index must be a contiguous zero-based sequence")
        return cls(
            sessions=pd.DatetimeIndex(pd.to_datetime(frame["date"], format="%Y-%m-%d")),
            sha256=digest,
            source=str(source_path),
        )

    def position(self, value: object) -> int:
        day = pd.Timestamp(value).normalize()
        try:
            return int(self.sessions.get_loc(day))
        except KeyError as exc:
            raise ValueError(f"{day.date()} is not in the frozen TSE session calendar") from exc

    def shift(self, value: object, offset: int) -> pd.Timestamp:
        index = self.position(value) + int(offset)
        if index < 0 or index >= len(self.sessions):
            raise ValueError(f"calendar horizon unavailable for {pd.Timestamp(value).date()} offset {offset}")
        return pd.Timestamp(self.sessions[index])

    def slice(self, start: object, end: object) -> pd.DatetimeIndex:
        first = pd.Timestamp(start).normalize()
        last = pd.Timestamp(end).normalize()
        return self.sessions[(self.sessions >= first) & (self.sessions <= last)]


def validate_sessions(values: Sequence[object]) -> pd.DatetimeIndex:
    sessions = pd.DatetimeIndex(pd.to_datetime(list(values), errors="raise")).normalize()
    if sessions.empty:
        raise ValueError("session list is empty")
    if sessions.has_duplicates or not sessions.is_monotonic_increasing:
        raise ValueError("sessions must be unique and sorted")
    return sessions
