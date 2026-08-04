"""HTTP MCP contract tests — in-process ASGI + fakes."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from tests.fakes.policy import read_only_policy
from tests.support import build_test_runtime as _btr

from lime_ref_postgres_mcp.bootstrap.settings import Settings
from lime_ref_postgres_mcp.domain.catalog.tool_catalog import ToolName
from lime_ref_postgres_mcp.presentation.mcp.server import MCP_HTTP_PATH, build_asgi_app


def _headers(token: str | None = "tok") -> dict[str, str]:
    h = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }
    if token is not None:
        h["Authorization"] = f"Bearer {token}"
    return h


async def _mcp_call(
    client: AsyncClient,
    method: str,
    params: dict[str, Any] | None,
    *,
    token: str | None = "tok",
    req_id: int = 1,
) -> dict[str, Any]:
    body: dict[str, Any] = {"jsonrpc": "2.0", "id": req_id, "method": method}
    if params is not None:
        body["params"] = params
    response = await client.post(MCP_HTTP_PATH, json=body, headers=_headers(token))
    assert response.status_code == 200, response.text
    return response.json()


@asynccontextmanager
async def _mcp_session(
    settings: Settings, **runtime_kwargs: Any
) -> AsyncIterator[tuple[AsyncClient, Any]]:
    tr = _btr.build_test_runtime(settings, **runtime_kwargs)
    server, app = build_asgi_app(tr.runtime, disable_dns_rebinding=True)
    transport = ASGITransport(app=app)
    async with server.session_manager.run():
        async with AsyncClient(transport=transport, base_url="http://127.0.0.1") as client:
            init = await _mcp_call(
                client,
                "initialize",
                {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "contract", "version": "0"},
                },
            )
            assert "result" in init
            await client.post(
                MCP_HTTP_PATH,
                json={"jsonrpc": "2.0", "method": "notifications/initialized"},
                headers=_headers(),
            )
            yield client, tr


@pytest.mark.asyncio
async def test_list_tools_eight(settings: Settings) -> None:
    async with _mcp_session(settings) as (client, _tr):
        data = await _mcp_call(client, "tools/list", {}, req_id=2)
        tools = data["result"]["tools"]
        assert len(tools) == 8
        names = {t["name"] for t in tools}
        assert names == {t.value for t in ToolName}


@pytest.mark.asyncio
async def test_missing_bearer(settings: Settings) -> None:
    async with _mcp_session(settings) as (client, tr):
        data = await _mcp_call(
            client,
            "tools/call",
            {"name": "list_schemas", "arguments": {}},
            token=None,
            req_id=3,
        )
        result = data["result"]
        assert result["isError"] is True
        envelope = json.loads(result["content"][0]["text"])
        assert envelope["status"] == "error"
        assert envelope["payload"]["code"] == "identity.passport_missing"
        assert tr.bus.events == []


@pytest.mark.asyncio
async def test_bad_bearer(settings: Settings) -> None:
    async with _mcp_session(settings) as (client, tr):
        data = await _mcp_call(
            client,
            "tools/call",
            {"name": "list_schemas", "arguments": {}},
            token="bad",
            req_id=4,
        )
        result = data["result"]
        assert result["isError"] is True
        envelope = json.loads(result["content"][0]["text"])
        assert envelope["payload"]["code"] == "identity.passport_invalid"
        assert tr.bus.events == []


@pytest.mark.asyncio
async def test_happy_list_schemas(settings: Settings) -> None:
    async with _mcp_session(settings) as (client, tr):
        data = await _mcp_call(
            client,
            "tools/call",
            {"name": "list_schemas", "arguments": {}},
            req_id=5,
        )
        result = data["result"]
        assert result["isError"] is False
        envelope = json.loads(result["content"][0]["text"])
        assert envelope["status"] == "ok"
        assert tr.bus.events
        assert tr.bus.events[0].status == "ok"


@pytest.mark.asyncio
async def test_capability_deny_emits(settings: Settings) -> None:
    async with _mcp_session(settings, policy=read_only_policy()) as (client, tr):
        data = await _mcp_call(
            client,
            "tools/call",
            {
                "name": "execute_write_query",
                "arguments": {"sql": "INSERT INTO t VALUES (1)"},
            },
            req_id=6,
        )
        result = data["result"]
        assert result["isError"] is True
        envelope = json.loads(result["content"][0]["text"])
        assert envelope["status"] == "denied"
        assert tr.bus.events
        assert tr.bus.events[0].outcome.reason_code == "capability_denied"
