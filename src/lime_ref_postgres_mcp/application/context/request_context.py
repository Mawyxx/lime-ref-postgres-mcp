"""RequestContext — post-whitelist correlation aggregate."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from lime_ref_postgres_mcp.domain.access.authorized_agent import AuthorizedAgent
from lime_ref_postgres_mcp.domain.access.policy import PolicyDocument
from lime_ref_postgres_mcp.domain.catalog.tool_catalog import ToolName


@dataclass(frozen=True, slots=True)
class PolicySnapshot:
    """Immutable policy document for the duration of one request."""

    document: PolicyDocument
    loaded_at: datetime


@dataclass(frozen=True, slots=True)
class RequestContext:
    """Authorized-path context — never carries Bearer / raw JWT."""

    request_id: str
    agent: AuthorizedAgent
    tool: ToolName
    args: Mapping[str, Any]
    started_at: datetime
    policy: PolicySnapshot


__all__ = ["PolicySnapshot", "RequestContext"]
