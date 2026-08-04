"""Derive LIME origin URL from JWKS URL for TokenVerifier(base_url=...)."""

from __future__ import annotations

from urllib.parse import urlparse

_JWKS_SUFFIX = "/.well-known/jwks.json"


def base_url_from_jwks_url(jwks_url: str) -> str:
    """Return scheme+netloc origin from a LIME JWKS URL.

    Accepts ``https://host/.well-known/jwks.json`` or bare origin URLs.
    Raises ``ValueError`` on invalid input.
    """
    raw = jwks_url.strip()
    if not raw:
        raise ValueError("LIME_JWKS_URL is empty")
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"Invalid LIME_JWKS_URL: {jwks_url!r}")
    origin = f"{parsed.scheme}://{parsed.netloc}"
    path = parsed.path.rstrip("/") or ""
    if path in {"", "/"}:
        return origin
    if path.endswith(_JWKS_SUFFIX) or path == _JWKS_SUFFIX:
        return origin
    raise ValueError(f"LIME_JWKS_URL must be origin or end with {_JWKS_SUFFIX}, got {jwks_url!r}")


__all__ = ["base_url_from_jwks_url"]
