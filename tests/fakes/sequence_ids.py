"""Deterministic ID generator for tests."""

from __future__ import annotations


class SequenceIds:
    def __init__(self, *, event_prefix: str = "evt", request_prefix: str = "req") -> None:
        self._event_n = 0
        self._request_n = 0
        self._event_prefix = event_prefix
        self._request_prefix = request_prefix

    def new_event_id(self) -> str:
        self._event_n += 1
        return f"{self._event_prefix}-{self._event_n}"

    def new_request_id(self) -> str:
        self._request_n += 1
        return f"{self._request_prefix}-{self._request_n}"


__all__ = ["SequenceIds"]
