"""Redaction deny-list tests."""

from __future__ import annotations

from lime_ref_postgres_mcp.bootstrap.observability.logging import build_record
from lime_ref_postgres_mcp.bootstrap.observability.redaction import sanitize_fields


def test_forbidden_keys_dropped() -> None:
    clean = sanitize_fields(
        {
            "tool": "select_rows",
            "bearer": "eyJhbGciOiJSUzI1NiJ9.aaa.bbb",
            "password": "secret",
            "postgres_url": "postgresql://u:p@h/db",
            "payload": {"rows": [1]},
            "rows": [1, 2],
            "authorization": "Bearer x",
            "jwt": "x.y.z",
        }
    )
    assert clean == {"tool": "select_rows"}


def test_build_record_redacts_forbidden() -> None:
    record = build_record(
        "mcp",
        "tools.call.start",
        bearer_token="secret-token",
        tool="list_schemas",
    )
    assert "bearer_token" not in record
    assert record["tool"] == "list_schemas"


def test_non_scalar_becomes_type_name() -> None:
    clean = sanitize_fields({"meta": {"a": 1}, "ok": True, "skip": None})
    assert clean["meta"] == "dict"
    assert clean["ok"] is True
    assert "skip" not in clean
