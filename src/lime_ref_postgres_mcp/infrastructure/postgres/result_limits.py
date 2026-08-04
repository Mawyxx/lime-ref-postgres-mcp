"""Row / byte limit enforcement and JSON-safe row normalization."""

from __future__ import annotations

import json
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any
from uuid import UUID

from lime_ref_postgres_mcp.domain.common.errors import DatabaseFault
from lime_ref_postgres_mcp.domain.common.result import Err, Ok, Result

_MSG_ROW = "Query result exceeds the allowed row limit"
_MSG_BYTE = "Query result exceeds the allowed size"
_MSG_SER = "Query result could not be safely serialized"


def payload_utf8_bytes(payload: Any) -> Result[int, DatabaseFault]:
    try:
        raw = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError):
        return Err(
            DatabaseFault(
                invariant_id="database.result_serialization_failed",
                message=_MSG_SER,
                context={},
            )
        )
    return Ok(len(raw))


def enforce_row_limit(row_count: int, max_rows: int) -> Result[None, DatabaseFault]:
    if row_count > max_rows:
        return Err(
            DatabaseFault(
                invariant_id="database.result_row_limit_exceeded",
                message=_MSG_ROW,
                context={},
            )
        )
    return Ok(None)


def enforce_byte_limit(payload: Any, max_bytes: int) -> Result[None, DatabaseFault]:
    measured = payload_utf8_bytes(payload)
    if isinstance(measured, Err):
        return Err(measured.error)
    if measured.value > max_bytes:
        return Err(
            DatabaseFault(
                invariant_id="database.result_byte_limit_exceeded",
                message=_MSG_BYTE,
                context={},
            )
        )
    return Ok(None)


def _normalize_scalar(value: Any) -> Any | None:
    """Return normalized scalar, or None if value needs container/binary handling."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    return None


def normalize_cell(value: Any) -> Any:
    scalar = _normalize_scalar(value)
    if scalar is not None or value is None:
        return scalar
    if isinstance(value, (bytes, memoryview)):
        raise TypeError("binary values are not JSON-serializable for agent payload")
    if isinstance(value, dict):
        return {str(k): normalize_cell(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [normalize_cell(v) for v in value]
    raise TypeError(f"unsupported cell type: {type(value).__name__}")


def records_to_rows(records: list[Any]) -> Result[list[dict[str, Any]], DatabaseFault]:
    rows: list[dict[str, Any]] = []
    try:
        for record in records:
            rows.append({k: normalize_cell(v) for k, v in dict(record).items()})
    except TypeError:
        return Err(
            DatabaseFault(
                invariant_id="database.result_serialization_failed",
                message=_MSG_SER,
                context={},
            )
        )
    return Ok(rows)


__all__ = [
    "enforce_byte_limit",
    "enforce_row_limit",
    "normalize_cell",
    "payload_utf8_bytes",
    "records_to_rows",
]
