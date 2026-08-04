"""Agent policy document: whitelist + capabilities + max_rows clamp."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from lime_ref_postgres_mcp.domain.access.capability import ToolCapability
from lime_ref_postgres_mcp.domain.agent.agent_id import AgentId
from lime_ref_postgres_mcp.domain.common.errors import AgentNotAllowlisted, InvariantViolation
from lime_ref_postgres_mcp.domain.common.result import Err, Ok, Result

DEFAULT_PERMISSIONS: frozenset[ToolCapability] = frozenset(
    {ToolCapability.READ_SCHEMA, ToolCapability.READ_DATA}
)

REASON_CAPABILITY_DENIED = "capability_denied"
REASON_STATEMENT_CLASS_DENIED = "statement_class_denied"
REASON_SQL_PARSE_FAULT = "sql_parse_fault"
REASON_DATABASE_FAULT = "database_fault"
REASON_TOOL_INPUT_INVALID = "tool_input_invalid"


def _violation(invariant_id: str, message: str, **context: Any) -> Err[InvariantViolation]:
    return Err(InvariantViolation(invariant_id=invariant_id, message=message, context=context))


def _parse_max_rows(raw: object) -> Result[int, InvariantViolation]:
    if not isinstance(raw, int) or isinstance(raw, bool) or raw < 1:
        return _violation(
            "policy.max_rows_invalid",
            "max_rows must be an integer >= 1",
            max_rows=raw,
        )
    return Ok(raw)


def _parse_capability_item(
    item: object, *, agent_id: str
) -> Result[ToolCapability, InvariantViolation]:
    if not isinstance(item, str):
        return _violation(
            "policy.capability_invalid",
            "capability must be a string",
            agent_id=agent_id,
            value=repr(item),
        )
    try:
        return Ok(ToolCapability(item))
    except ValueError:
        return _violation(
            "policy.capability_unknown",
            "unknown capability in policy",
            agent_id=agent_id,
            capability=item,
        )


def _parse_permissions(
    perms_raw: object, *, agent_id: str
) -> Result[frozenset[ToolCapability], InvariantViolation]:
    if not isinstance(perms_raw, list):
        return _violation(
            "policy.permissions_invalid",
            "permissions must be a list",
            agent_id=agent_id,
        )
    caps: set[ToolCapability] = set()
    for item in perms_raw:
        parsed = _parse_capability_item(item, agent_id=agent_id)
        if isinstance(parsed, Err):
            return Err(parsed.error)
        caps.add(parsed.value)
    return Ok(frozenset(caps))


def _parse_agent_entry(
    raw_id: object, entry: object
) -> Result[tuple[str, frozenset[ToolCapability]], InvariantViolation]:
    id_raw = raw_id if isinstance(raw_id, str) else str(raw_id)
    parsed_id = AgentId.parse(id_raw)
    if isinstance(parsed_id, Err):
        return Err(parsed_id.error)
    agent_key = parsed_id.value.value
    if not isinstance(entry, Mapping):
        return _violation(
            "policy.agent_entry_invalid",
            "agent entry must be a mapping",
            agent_id=agent_key,
        )
    if "permissions" not in entry:
        return Ok((agent_key, DEFAULT_PERMISSIONS))
    perms = _parse_permissions(entry["permissions"], agent_id=agent_key)
    if isinstance(perms, Err):
        return Err(perms.error)
    return Ok((agent_key, perms.value))


def _parse_agents(
    agents_raw: object,
) -> Result[dict[str, frozenset[ToolCapability]], InvariantViolation]:
    if not isinstance(agents_raw, Mapping):
        return _violation("policy.agents_invalid", "agents must be a mapping")
    agents: dict[str, frozenset[ToolCapability]] = {}
    for raw_id, entry in agents_raw.items():
        parsed = _parse_agent_entry(raw_id, entry)
        if isinstance(parsed, Err):
            return Err(parsed.error)
        key, caps = parsed.value
        agents[key] = caps
    return Ok(agents)


@dataclass(frozen=True, slots=True)
class AgentPolicy:
    """Whitelist slice for one agent."""

    agent_id: AgentId
    permissions: frozenset[ToolCapability]

    def has(self, cap: ToolCapability) -> bool:
        return cap in self.permissions

    def has_all(self, required: set[ToolCapability] | frozenset[ToolCapability]) -> bool:
        return required <= self.permissions


@dataclass(frozen=True, slots=True)
class PolicyDocument:
    """Immutable agents policy snapshot."""

    max_rows: int
    agents: Mapping[str, frozenset[ToolCapability]]

    def resolve(self, agent_id: AgentId) -> Result[AgentPolicy, AgentNotAllowlisted]:
        key = agent_id.value
        if key not in self.agents:
            return Err(
                AgentNotAllowlisted(
                    invariant_id="access.agent_not_allowlisted",
                    message="agent is not on the allowlist",
                    context={"agent_id": key},
                )
            )
        return Ok(AgentPolicy(agent_id=agent_id, permissions=self.agents[key]))

    def clamp_limit(self, requested: int | None) -> int:
        if requested is None or requested < 1:
            return self.max_rows
        return min(requested, self.max_rows)

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> Result[PolicyDocument, InvariantViolation]:
        if not isinstance(data, Mapping):
            return _violation("policy.document_invalid", "policy root must be a mapping")
        max_rows = _parse_max_rows(data.get("max_rows"))
        if isinstance(max_rows, Err):
            return Err(max_rows.error)
        agents = _parse_agents(data.get("agents"))
        if isinstance(agents, Err):
            return Err(agents.error)
        return Ok(cls(max_rows=max_rows.value, agents=agents.value))


__all__ = [
    "DEFAULT_PERMISSIONS",
    "REASON_CAPABILITY_DENIED",
    "REASON_DATABASE_FAULT",
    "REASON_SQL_PARSE_FAULT",
    "REASON_STATEMENT_CLASS_DENIED",
    "REASON_TOOL_INPUT_INVALID",
    "AgentPolicy",
    "PolicyDocument",
]
