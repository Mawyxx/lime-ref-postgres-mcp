"""Fake AgentPolicyStore."""

from __future__ import annotations

from lime_ref_postgres_mcp.domain.access.capability import ToolCapability
from lime_ref_postgres_mcp.domain.access.policy import PolicyDocument
from lime_ref_postgres_mcp.domain.common.errors import PolicyStoreFault
from lime_ref_postgres_mcp.domain.common.result import Err, Ok, Result, unwrap


class FakePolicyStore:
    def __init__(self, document: PolicyDocument | None = None) -> None:
        if document is None:
            document = unwrap(
                PolicyDocument.from_mapping(
                    {
                        "max_rows": 100,
                        "agents": {
                            "agent_ok": {"permissions": ["READ_SCHEMA", "READ_DATA", "WRITE_DATA"]},
                            "agent_read": {"permissions": ["READ_SCHEMA", "READ_DATA"]},
                        },
                    }
                )
            )
        self.document = document
        self.fault: PolicyStoreFault | None = None

    async def current(self) -> Result[PolicyDocument, PolicyStoreFault]:
        if self.fault is not None:
            return Err(self.fault)
        return Ok(self.document)


def read_only_policy() -> PolicyDocument:
    return unwrap(
        PolicyDocument.from_mapping(
            {
                "max_rows": 50,
                "agents": {
                    "agent_ok": {"permissions": ["READ_SCHEMA", "READ_DATA"]},
                },
            }
        )
    )


def write_policy() -> PolicyDocument:
    return unwrap(
        PolicyDocument.from_mapping(
            {
                "max_rows": 100,
                "agents": {
                    "agent_ok": {
                        "permissions": [
                            ToolCapability.READ_SCHEMA.value,
                            ToolCapability.READ_DATA.value,
                            ToolCapability.WRITE_DATA.value,
                        ]
                    },
                },
            }
        )
    )


__all__ = ["FakePolicyStore", "read_only_policy", "write_policy"]
