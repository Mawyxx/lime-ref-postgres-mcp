"""InvokeAgentToolCommand — pre-auth transport/application input."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from lime_ref_postgres_mcp.domain.catalog.tool_catalog import ToolName


@dataclass(frozen=True, slots=True)
class InvokeAgentToolCommand:
    """Raw tool call before passport + whitelist."""

    bearer_token: str | None
    tool: ToolName
    args: Mapping[str, Any]
    request_id: str | None = None


__all__ = ["InvokeAgentToolCommand"]
