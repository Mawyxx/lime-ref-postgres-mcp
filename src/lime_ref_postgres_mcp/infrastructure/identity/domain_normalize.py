"""Hostname normalize for MCP domain pin (ADR 0095)."""

from __future__ import annotations

from urllib.parse import urlparse


def _reject_ip(host: str) -> None:
    if host.replace(".", "").isdigit() or ":" in host or host.startswith("["):
        raise ValueError("domain must not be an IP address")


def _from_url(text: str) -> str:
    parsed = urlparse(text)
    if parsed.username or parsed.password:
        raise ValueError("domain must not include userinfo")
    if parsed.port is not None:
        raise ValueError("domain must not include a port")
    return parsed.hostname or ""


def _from_plain(text: str) -> str:
    if "@" in text:
        raise ValueError("domain must not include userinfo")
    if ":" in text:
        raise ValueError("domain must not include a port")
    if "/" in text:
        return text.split("/", 1)[0]
    return text


def normalize_mcp_domain(raw: str) -> str:
    """Normalize to hostname only — lower, strip scheme/path; reject port/IP/userinfo."""
    text = raw.strip()
    if not text:
        raise ValueError("domain must be non-empty")
    candidate = _from_url(text) if "://" in text else _from_plain(text)
    host = candidate.strip().lower().rstrip(".")
    if not host:
        raise ValueError("domain must be non-empty")
    _reject_ip(host)
    return host


__all__ = ["normalize_mcp_domain"]
