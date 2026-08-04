"""MCP server dispatch unit tests (in-process handlers, no TCP)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest
from mcp.server import ServerRequestContext
from mcp.types import CallToolRequestParams
from tests.support.build_test_runtime import build_test_runtime

from lime_ref_postgres_mcp.bootstrap.settings import Settings
from lime_ref_postgres_mcp.presentation.mcp.server import build_mcp_server


@pytest.mark.asyncio
async def test_on_call_tool_unknown(settings: Settings) -> None:
    tr = build_test_runtime(settings)
    server = build_mcp_server(tr.runtime)
    entry = server.get_request_handler("tools/call")
    assert entry is not None
    ctx = MagicMock(spec=ServerRequestContext)
    ctx.request = MagicMock()
    ctx.request.headers = {"Authorization": "Bearer tok"}
    result = await entry.handler(ctx, CallToolRequestParams(name="nope", arguments={}))
    body = json.loads(result.content[0].text)
    assert result.is_error is True
    assert body["payload"]["code"] == "mcp.unknown_tool"


@pytest.mark.asyncio
async def test_on_call_tool_list_schemas(settings: Settings) -> None:
    tr = build_test_runtime(settings)
    server = build_mcp_server(tr.runtime)
    entry = server.get_request_handler("tools/call")
    assert entry is not None
    ctx = MagicMock(spec=ServerRequestContext)
    ctx.request = MagicMock()
    ctx.request.headers = {"Authorization": "Bearer tok"}
    result = await entry.handler(ctx, CallToolRequestParams(name="list_schemas", arguments={}))
    assert result.is_error is False
    assert json.loads(result.content[0].text)["status"] == "ok"


@pytest.mark.asyncio
async def test_on_list_tools(settings: Settings) -> None:
    tr = build_test_runtime(settings)
    server = build_mcp_server(tr.runtime)
    entry = server.get_request_handler("tools/list")
    assert entry is not None
    ctx = MagicMock(spec=ServerRequestContext)
    result = await entry.handler(ctx, None)
    assert len(result.tools) == 8


@pytest.mark.asyncio
async def test_missing_request_means_no_bearer(settings: Settings) -> None:
    tr = build_test_runtime(settings)
    server = build_mcp_server(tr.runtime)
    entry = server.get_request_handler("tools/call")
    assert entry is not None
    ctx = MagicMock(spec=ServerRequestContext)
    ctx.request = None
    result = await entry.handler(ctx, CallToolRequestParams(name="list_schemas", arguments={}))
    assert result.is_error is True
    assert json.loads(result.content[0].text)["status"] == "error"


@pytest.mark.asyncio
async def test_traceparent_headers_none(settings: Settings) -> None:
    tr = build_test_runtime(settings)
    server = build_mcp_server(tr.runtime)
    entry = server.get_request_handler("tools/call")
    assert entry is not None
    ctx = MagicMock(spec=ServerRequestContext)
    ctx.request = MagicMock()
    ctx.request.headers = None
    result = await entry.handler(ctx, CallToolRequestParams(name="list_schemas", arguments={}))
    assert result.is_error is True


@pytest.mark.asyncio
async def test_traceparent_bound_on_call(settings: Settings) -> None:
    tr = build_test_runtime(settings)
    server = build_mcp_server(tr.runtime)
    entry = server.get_request_handler("tools/call")
    assert entry is not None
    ctx = MagicMock(spec=ServerRequestContext)
    ctx.request = MagicMock()
    ctx.request.headers = {
        "Authorization": "Bearer tok",
        "traceparent": "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01",
    }
    result = await entry.handler(ctx, CallToolRequestParams(name="list_schemas", arguments={}))
    assert result.is_error is False


@pytest.mark.asyncio
async def test_outcome_fallback_when_content_invalid(
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from mcp.types import CallToolResult, TextContent

    from lime_ref_postgres_mcp.presentation.mcp import server as server_mod

    tr = build_test_runtime(settings)
    server = build_mcp_server(tr.runtime)
    entry = server.get_request_handler("tools/call")
    assert entry is not None

    async def weird_handler(*_a: object, **_k: object) -> CallToolResult:
        return CallToolResult(
            content=[TextContent(type="text", text="not-json")],
            is_error=False,
        )

    monkeypatch.setitem(server_mod._HANDLERS, list(server_mod._HANDLERS.keys())[0], weird_handler)
    ctx = MagicMock(spec=ServerRequestContext)
    ctx.request = MagicMock()
    ctx.request.headers = {"Authorization": "Bearer tok"}
    result = await entry.handler(ctx, CallToolRequestParams(name="list_schemas", arguments={}))
    assert result.is_error is False


@pytest.mark.asyncio
async def test_outcome_unknown_status_uses_is_error(
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from mcp.types import CallToolResult, TextContent

    from lime_ref_postgres_mcp.presentation.mcp import server as server_mod

    tr = build_test_runtime(settings)
    server = build_mcp_server(tr.runtime)
    entry = server.get_request_handler("tools/call")
    assert entry is not None

    async def odd_status(*_a: object, **_k: object) -> CallToolResult:
        return CallToolResult(
            content=[TextContent(type="text", text='{"status":"weird"}')],
            is_error=True,
        )

    monkeypatch.setitem(server_mod._HANDLERS, list(server_mod._HANDLERS.keys())[0], odd_status)
    ctx = MagicMock(spec=ServerRequestContext)
    ctx.request = MagicMock()
    ctx.request.headers = {"Authorization": "Bearer tok"}
    result = await entry.handler(ctx, CallToolRequestParams(name="list_schemas", arguments={}))
    assert result.is_error is True
