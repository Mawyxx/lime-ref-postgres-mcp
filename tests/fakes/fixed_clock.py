"""Deterministic clock for tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta


class FixedClock:
    def __init__(self, start: datetime | None = None) -> None:
        self._now = start or datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC)

    def now_utc(self) -> datetime:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now = self._now + timedelta(seconds=seconds)


__all__ = ["FixedClock"]
