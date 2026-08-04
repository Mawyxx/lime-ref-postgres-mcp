"""Correlation contextvars + W3C traceparent parse (no OTel SDK)."""

from __future__ import annotations

import contextvars
import re
from typing import Any

_BOUND: contextvars.ContextVar[dict[str, object] | None] = contextvars.ContextVar(
    "lime_mcp_obs_bound",
    default=None,
)

_TRACEPARENT_RE = re.compile(
    r"^([0-9a-f]{2})-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})$",
    re.IGNORECASE,
)


def get_bound() -> dict[str, object]:
    current = _BOUND.get()
    return dict(current) if current else {}


def bind_context(**fields: object) -> None:
    """Merge non-None fields into the current task-local dict."""
    current = dict(_BOUND.get() or {})
    for key, value in fields.items():
        if value is None:
            continue
        current[key] = value
    _BOUND.set(current)


def clear_context() -> None:
    _BOUND.set({})


def parse_traceparent(raw: str | None) -> dict[str, str]:
    """Best-effort W3C traceparent → ``trace_id`` / ``parent_span_id``."""
    if raw is None:
        return {}
    text = raw.strip()
    if not text:
        return {}
    match = _TRACEPARENT_RE.match(text)
    if match is None:
        return {}
    return {
        "trace_id": match.group(2).lower(),
        "parent_span_id": match.group(3).lower(),
    }


def merge_for_log(**fields: Any) -> dict[str, Any]:
    merged: dict[str, Any] = dict(get_bound())
    for key, value in fields.items():
        if value is None:
            continue
        merged[key] = value
    return merged


__all__ = [
    "bind_context",
    "clear_context",
    "get_bound",
    "merge_for_log",
    "parse_traceparent",
]
