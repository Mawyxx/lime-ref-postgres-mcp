"""JSONL / console renderers for process log records."""

from __future__ import annotations

import json
import sys
import time
from datetime import UTC, datetime
from typing import Any, TextIO

from lime_ref_postgres_mcp.bootstrap.observability.context import merge_for_log
from lime_ref_postgres_mcp.bootstrap.observability.redaction import sanitize_fields
from lime_ref_postgres_mcp.bootstrap.observability.schema import SCHEMA_ID

_LEVELS = {
    "DEBUG": 10,
    "INFO": 20,
    "WARNING": 30,
    "ERROR": 40,
}

_configured = False
_min_level = 20
_format = "json"
_stream_name = "stderr"
_custom_stream: TextIO | None = None


def _iso_ts() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def reset_logging_state_for_tests() -> None:
    global _configured, _min_level, _format, _stream_name, _custom_stream
    _configured = False
    _min_level = 20
    _format = "json"
    _stream_name = "stderr"
    _custom_stream = None


def is_configured() -> bool:
    return _configured


def apply_logging_config(
    *,
    level: str,
    format: str,
    stream_name: str = "stderr",
    stream: TextIO | None = None,
) -> None:
    global _configured, _min_level, _format, _stream_name, _custom_stream
    level_key = level.strip().upper()
    if level_key not in _LEVELS:
        level_key = "INFO"
    _min_level = _LEVELS[level_key]
    _format = format if format in {"json", "console"} else "json"
    if stream is not None:
        _custom_stream = stream
        _stream_name = "custom"
    else:
        _custom_stream = None
        _stream_name = stream_name if stream_name in {"stderr", "stdout"} else "stderr"
    _configured = True


def _resolve_stream() -> TextIO:
    if _custom_stream is not None:
        return _custom_stream
    return sys.stdout if _stream_name == "stdout" else sys.stderr


def build_record(
    component: str,
    event: str,
    *,
    level: str = "INFO",
    **fields: Any,
) -> dict[str, object]:
    level_key = level.strip().upper()
    if level_key not in _LEVELS:
        level_key = "INFO"
    merged = merge_for_log(**fields)
    safe = sanitize_fields(merged)
    record: dict[str, object] = {
        "schema": SCHEMA_ID,
        "ts": _iso_ts(),
        "level": level_key,
        "component": component,
        "event": event,
    }
    record.update(safe)
    return record


def render_json(record: dict[str, object]) -> str:
    return json.dumps(record, ensure_ascii=False, separators=(",", ":"), default=str)


def render_console(record: dict[str, object]) -> str:
    parts = [
        str(record.get("ts", "")),
        str(record.get("level", "INFO")),
        f"lime.{record.get('component', '?')}",
        f"event={record.get('event', '')}",
    ]
    for key, value in record.items():
        if key in {"schema", "ts", "level", "component", "event"}:
            continue
        parts.append(f"{key}={value}")
    return " ".join(parts)


def emit_record(record: dict[str, object]) -> None:
    level_key = str(record.get("level", "INFO"))
    if _LEVELS.get(level_key, 20) < _min_level:
        return
    line = render_json(record) if _format == "json" else render_console(record)
    try:
        print(line, file=_resolve_stream(), flush=True)
    except Exception:
        return


def log(component: str, event: str, *, level: str = "INFO", **fields: Any) -> None:
    """Emit one schema v1 process log line. Never raises to callers."""
    try:
        record = build_record(component, event, level=level, **fields)
        emit_record(record)
    except Exception:
        return


def monotonic_ms() -> float:
    return time.monotonic() * 1000.0


__all__ = [
    "apply_logging_config",
    "build_record",
    "emit_record",
    "is_configured",
    "log",
    "monotonic_ms",
    "render_console",
    "render_json",
    "reset_logging_state_for_tests",
]
