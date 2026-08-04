"""Unit tests for process log schema records."""

from __future__ import annotations

from lime_ref_postgres_mcp.bootstrap.observability.logging import build_record
from lime_ref_postgres_mcp.bootstrap.observability.schema import SCHEMA_ID


def test_build_record_required_fields() -> None:
    record = build_record("mcp", "tools.call.done", tool="select_rows", outcome="ok")
    assert record["schema"] == SCHEMA_ID
    assert "ts" in record and str(record["ts"]).endswith("Z")
    assert record["level"] == "INFO"
    assert record["component"] == "mcp"
    assert record["event"] == "tools.call.done"
    assert record["tool"] == "select_rows"
    assert record["outcome"] == "ok"


def test_build_record_skips_none() -> None:
    record = build_record("serve", "serve.start", host="127.0.0.1", port=None)
    assert "port" not in record
    assert record["host"] == "127.0.0.1"
