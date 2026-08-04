"""configure_observability idempotency + format."""

from __future__ import annotations

import io

import pytest

from lime_ref_postgres_mcp.bootstrap.observability.configure import (
    configure_observability,
    reset_configure_for_tests,
)
from lime_ref_postgres_mcp.bootstrap.observability.logging import (
    build_record,
    emit_record,
    is_configured,
    render_console,
    render_json,
)
from lime_ref_postgres_mcp.bootstrap.observability.metrics import metrics


def setup_function() -> None:
    reset_configure_for_tests()


def test_configure_idempotent() -> None:
    buf = io.StringIO()
    configure_observability(level="DEBUG", format="json", stream=buf, metrics_enabled=True)
    configure_observability(level="INFO", format="console", stream=buf, metrics_enabled=False)
    assert is_configured()
    assert metrics.snapshot()["counters"] == {}  # reset not called; set_enabled False
    metrics.inc("x")
    assert metrics.snapshot()["counters"] == {}


def test_json_and_console_render() -> None:
    record = build_record("serve", "serve.start", host="127.0.0.1")
    assert '"schema"' in render_json(record)
    console = render_console(record)
    assert "event=serve.start" in console
    assert "host=127.0.0.1" in console


def test_emit_respects_level() -> None:
    buf = io.StringIO()
    configure_observability(level="ERROR", format="json", stream=buf)
    emit_record(build_record("mcp", "tools.call.start", level="INFO"))
    assert buf.getvalue() == ""
    emit_record(build_record("serve", "config.error", level="ERROR"))
    assert "config.error" in buf.getvalue()


def test_was_configured_and_invalid_levels() -> None:
    from lime_ref_postgres_mcp.bootstrap.observability.configure import was_configured
    from lime_ref_postgres_mcp.bootstrap.observability.logging import apply_logging_config, log

    assert was_configured() is False
    buf = io.StringIO()
    apply_logging_config(level="NOPE", format="weird", stream=buf)
    assert was_configured() is True
    record = build_record("x", "y", level="NOPE")
    assert record["level"] == "INFO"
    log("serve", "composition.ok")
    assert "composition.ok" in buf.getvalue()


def test_log_swallows_emit_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    from lime_ref_postgres_mcp.bootstrap.observability import logging as logging_mod

    def boom(*_a: object, **_k: object) -> dict[str, object]:
        raise RuntimeError("boom")

    monkeypatch.setattr(logging_mod, "build_record", boom)
    logging_mod.log("serve", "x")  # must not raise


def test_emit_record_swallows_print_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    class BoomStream:
        def write(self, *_a: object, **_k: object) -> int:
            raise OSError("closed")

        def flush(self) -> None:
            return None

    configure_observability(level="DEBUG", format="json", stream=BoomStream())  # type: ignore[arg-type]
    emit_record(build_record("serve", "composition.ok"))
