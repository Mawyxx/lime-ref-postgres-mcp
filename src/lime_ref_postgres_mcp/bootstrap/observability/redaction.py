"""Deny-list field sanitizer for process logs (ADR-003 / OWASP A09)."""

from __future__ import annotations

from typing import Any

FORBIDDEN_KEYS = frozenset(
    {
        "authorization",
        "bearer",
        "bearer_token",
        "token",
        "passport",
        "password",
        "secret",
        "api_key",
        "postgres_url",
        "payload",
        "rows",
        "response",
        "body",
        "result",
        "jwt",
    }
)

_SCALAR = (str, int, float, bool)


def sanitize_fields(fields: dict[str, Any]) -> dict[str, object]:
    """Drop forbidden keys; coerce values to safe scalars."""
    out: dict[str, object] = {}
    for key, value in fields.items():
        if value is None:
            continue
        if key.lower() in FORBIDDEN_KEYS:
            continue
        if isinstance(value, _SCALAR):
            out[key] = value
        else:
            out[key] = type(value).__name__
    return out


__all__ = ["FORBIDDEN_KEYS", "sanitize_fields"]
