"""Bearer extraction — passport never in tool args (ADR-001)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def extract_bearer(source: Mapping[str, str] | Any) -> str | None:
    """Return Bearer token or None (→ PassportMissing). Never logs the token."""
    headers = _as_headers(source)
    raw = _header_get(headers, "authorization")
    if raw is None:
        return None
    parts = raw.split(None, 1)
    if len(parts) != 2:
        return None
    scheme, token = parts
    if scheme.lower() != "bearer":
        return None
    stripped = token.strip()
    return stripped or None


def header_get(headers: Mapping[str, str] | Any, name: str) -> str | None:
    return _header_get(headers, name)


def _as_headers(source: Mapping[str, str] | Any) -> Mapping[str, str] | Any:
    # Starlette Request is a Mapping (path params). Prefer .headers when distinct.
    headers_attr = getattr(source, "headers", None)
    if headers_attr is not None and headers_attr is not source:
        return headers_attr
    return source


def _header_get(headers: Mapping[str, str] | Any, name: str) -> str | None:
    getter = getattr(headers, "get", None)
    if callable(getter):
        for candidate in (name, name.title(), name.upper()):
            value = getter(candidate)
            if isinstance(value, str):
                return value
    if isinstance(headers, Mapping):
        for key, value in headers.items():
            if str(key).lower() == name.lower() and isinstance(value, str):
                return value
    return None


__all__ = ["extract_bearer", "header_get"]
