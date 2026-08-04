"""domain_normalize unit tests."""

from __future__ import annotations

import pytest

from lime_ref_postgres_mcp.infrastructure.identity.domain_normalize import normalize_mcp_domain


def test_normalize_plain() -> None:
    assert normalize_mcp_domain("Example.COM") == "example.com"


def test_normalize_strips_scheme_path() -> None:
    assert normalize_mcp_domain("https://Example.com/path") == "example.com"


def test_normalize_rejects_port() -> None:
    with pytest.raises(ValueError, match="port"):
        normalize_mcp_domain("example.com:443")


def test_normalize_rejects_port_in_url() -> None:
    with pytest.raises(ValueError, match="port"):
        normalize_mcp_domain("https://example.com:443/")


def test_normalize_rejects_userinfo() -> None:
    with pytest.raises(ValueError, match="userinfo"):
        normalize_mcp_domain("https://user:pass@example.com/")


def test_normalize_rejects_userinfo_plain() -> None:
    with pytest.raises(ValueError, match="userinfo"):
        normalize_mcp_domain("user@example.com")


def test_normalize_strips_path_without_scheme() -> None:
    assert normalize_mcp_domain("example.com/foo") == "example.com"


def test_normalize_rejects_empty() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        normalize_mcp_domain("   ")


def test_normalize_rejects_empty_after_parse() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        normalize_mcp_domain("https:///path")


def test_normalize_rejects_ip() -> None:
    with pytest.raises(ValueError, match="IP"):
        normalize_mcp_domain("127.0.0.1")


def test_normalize_rejects_ipv6() -> None:
    with pytest.raises(ValueError):
        normalize_mcp_domain("[::1]")
