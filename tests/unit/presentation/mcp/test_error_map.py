"""map_to_mcp unit tests."""

from __future__ import annotations

import json

from mcp.types import TextContent

from lime_ref_postgres_mcp.application.context.agent_reply import AgentReply
from lime_ref_postgres_mcp.domain.common.errors import PassportMissing
from lime_ref_postgres_mcp.domain.common.result import Err, Ok
from lime_ref_postgres_mcp.presentation.mcp.error_map import map_to_mcp


def _text(result: object) -> dict[str, object]:
    content = result.content  # type: ignore[attr-defined]
    assert len(content) == 1
    assert isinstance(content[0], TextContent)
    return json.loads(content[0].text)


def test_ok_reply() -> None:
    mapped = map_to_mcp(Ok(AgentReply(status="ok", payload={"schemas": ["public"]})))
    assert mapped.is_error is False
    assert _text(mapped) == {"status": "ok", "payload": {"schemas": ["public"]}}


def test_denied_reply_is_error() -> None:
    mapped = map_to_mcp(Ok(AgentReply(status="denied", payload={"error": "no", "code": "x"})))
    assert mapped.is_error is True
    assert _text(mapped)["status"] == "denied"


def test_error_reply_is_error() -> None:
    mapped = map_to_mcp(Ok(AgentReply(status="error", payload={"error": "db"})))
    assert mapped.is_error is True


def test_preauth_err_no_context_leak() -> None:
    err = PassportMissing(
        invariant_id="identity.passport_missing",
        message="Authorization Bearer token is missing",
        context={"secret": "should-not-appear"},
    )
    mapped = map_to_mcp(Err(err))
    assert mapped.is_error is True
    body = _text(mapped)
    assert body == {
        "status": "error",
        "payload": {
            "error": "Authorization Bearer token is missing",
            "code": "identity.passport_missing",
        },
    }
    assert "secret" not in json.dumps(body)
