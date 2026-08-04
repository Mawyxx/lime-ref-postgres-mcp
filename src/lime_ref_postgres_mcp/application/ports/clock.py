"""Injectable time and ID generation (Prime A15)."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol


class Clock(Protocol):
    def now_utc(self) -> datetime: ...


class IdGenerator(Protocol):
    def new_event_id(self) -> str: ...

    def new_request_id(self) -> str: ...


__all__ = ["Clock", "IdGenerator"]
