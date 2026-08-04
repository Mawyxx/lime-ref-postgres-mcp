"""ConsoleSink — JSONL stdout audit subscriber (no agent payload)."""

from __future__ import annotations

import json
import sys
from datetime import UTC
from typing import Any, TextIO

from lime_ref_postgres_mcp.domain.auditing.agent_action_event import AgentActionEvent
from lime_ref_postgres_mcp.domain.auditing.event_outcome import EventOutcome

_FORBIDDEN = frozenset({"payload", "response", "rows", "result", "body"})


class ConsoleSink:
    """Compact JSON line per AgentActionEvent; flush immediately."""

    def __init__(self, stream: TextIO | None = None) -> None:
        self._stream = sys.stdout if stream is None else stream

    async def __call__(self, event: AgentActionEvent) -> None:
        record = _event_record(event)
        line = json.dumps(record, default=str, separators=(",", ":"))
        print(line, file=self._stream, flush=True)


def _event_record(event: AgentActionEvent) -> dict[str, Any]:
    request = dict(event.request)
    for key in _FORBIDDEN:
        request.pop(key, None)
    record: dict[str, Any] = {
        "event_id": event.event_id,
        "ts": _ts_z(event),
        "agent_id": str(event.agent_id),
        "request": {
            "tool": request.get("tool"),
            "args": request.get("args", {}),
        },
        "status": event.status,
        "outcome": _outcome_dict(event.outcome),
        "duration_ms": event.duration_ms,
        "meta": dict(event.meta),
    }
    return record


def _ts_z(event: AgentActionEvent) -> str:
    ts = event.ts
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    else:
        ts = ts.astimezone(UTC)
    return ts.isoformat().replace("+00:00", "Z")


def _outcome_dict(outcome: EventOutcome) -> dict[str, Any]:
    data: dict[str, Any] = {}
    if outcome.reason_code is not None:
        data["reason_code"] = outcome.reason_code
    if outcome.missing_capabilities:
        data["missing_capabilities"] = list(outcome.missing_capabilities)
    if outcome.statement_class is not None:
        data["statement_class"] = outcome.statement_class
    if outcome.rows_count is not None:
        data["rows_count"] = outcome.rows_count
    if outcome.affected_rows is not None:
        data["affected_rows"] = outcome.affected_rows
    return data


__all__ = ["ConsoleSink"]
