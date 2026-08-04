"""Idempotent process observability bootstrap (serve / composition only)."""

from __future__ import annotations

from typing import TextIO

from lime_ref_postgres_mcp.bootstrap.observability.logging import (
    apply_logging_config,
    is_configured,
)
from lime_ref_postgres_mcp.bootstrap.observability.metrics import metrics

_configured_once = False


def configure_observability(
    *,
    level: str = "INFO",
    format: str = "json",
    stream: TextIO | None = None,
    stream_name: str = "stderr",
    metrics_enabled: bool = True,
) -> None:
    """Attach process log handler settings + metrics switch. Idempotent."""
    global _configured_once
    apply_logging_config(
        level=level,
        format=format,
        stream_name=stream_name,
        stream=stream,
    )
    metrics.set_enabled(metrics_enabled)
    _configured_once = True


def reset_configure_for_tests() -> None:
    global _configured_once
    _configured_once = False
    from lime_ref_postgres_mcp.bootstrap.observability.logging import (
        reset_logging_state_for_tests,
    )

    reset_logging_state_for_tests()
    metrics.reset(enabled=True)


def was_configured() -> bool:
    return _configured_once or is_configured()


__all__ = ["configure_observability", "reset_configure_for_tests", "was_configured"]
