"""AgentReply — full tool result for MCP presentation only."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

ReplyStatus = Literal["ok", "error", "denied"]


@dataclass(frozen=True, slots=True)
class AgentReply:
    """Payload returns only to presentation — never into EventBus."""

    status: ReplyStatus
    payload: Any


__all__ = ["AgentReply", "ReplyStatus"]
