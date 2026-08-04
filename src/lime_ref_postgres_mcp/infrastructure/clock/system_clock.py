"""Production Clock adapter — wall clock UTC."""

from __future__ import annotations

from datetime import UTC, datetime


class SystemClock:
    def now_utc(self) -> datetime:
        return datetime.now(UTC)
