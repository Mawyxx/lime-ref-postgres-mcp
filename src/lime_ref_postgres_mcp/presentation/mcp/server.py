"""MCP Server + Streamable HTTP ASGI app (official low-level Server)."""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from contextlib import asynccontextmanager
from typing import Any

from mcp.server import Server, ServerRequestContext
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import (
    CallToolRequestParams,
    CallToolResult,
    ListToolsResult,
    PaginatedRequestParams,
    TextContent,
)
from starlette.applications import Starlette

from lime_ref_postgres_mcp.application.services.invoke_agent_tool import InvokeAgentToolService
from lime_ref_postgres_mcp.bootstrap.container import Runtime
from lime_ref_postgres_mcp.bootstrap.observability import (
    bind_context,
    clear_context,
    log,
    metrics,
    monotonic_ms,
    parse_traceparent,
)
from lime_ref_postgres_mcp.domain.catalog.tool_catalog import ToolName
from lime_ref_postgres_mcp.infrastructure.identity.lime_passport_verifier import (
    LimePassportVerifier,
)
from lime_ref_postgres_mcp.infrastructure.postgres.asyncpg_database_gateway import (
    AsyncpgDatabaseGateway,
)
from lime_ref_postgres_mcp.presentation.mcp.auth import extract_bearer, header_get
from lime_ref_postgres_mcp.presentation.mcp.handlers import admin_tools, data_tools, schema_tools
from lime_ref_postgres_mcp.presentation.mcp.tool_specs import list_tool_specs

MCP_HTTP_PATH = "/mcp"

ToolHandler = Callable[
    [InvokeAgentToolService, str | None, Mapping[str, Any], str],
    Awaitable[CallToolResult],
]

_HANDLERS: dict[ToolName, ToolHandler] = {
    ToolName.LIST_SCHEMAS: schema_tools.list_schemas,
    ToolName.LIST_TABLES: schema_tools.list_tables,
    ToolName.GET_TABLE_SCHEMA: schema_tools.get_table_schema,
    ToolName.SELECT_ROWS: data_tools.select_rows,
    ToolName.EXECUTE_READONLY_QUERY: data_tools.execute_readonly_query,
    ToolName.EXPLAIN_QUERY_PLAN: data_tools.explain_query_plan,
    ToolName.EXECUTE_WRITE_QUERY: data_tools.execute_write_query,
    ToolName.GET_DATABASE_STATS: admin_tools.get_database_stats,
}


def _unknown_tool(name: str) -> CallToolResult:
    envelope = {
        "status": "error",
        "payload": {"error": f"Unknown tool: {name}", "code": "mcp.unknown_tool"},
    }
    return CallToolResult(
        content=[TextContent(type="text", text=json.dumps(envelope))],
        is_error=True,
    )


def _bearer_from_ctx(ctx: ServerRequestContext[Any, Any]) -> str | None:
    if ctx.request is None:
        return None
    return extract_bearer(ctx.request)


def _traceparent_from_ctx(ctx: ServerRequestContext[Any, Any]) -> str | None:
    if ctx.request is None:
        return None
    headers = getattr(ctx.request, "headers", None)
    if headers is None:
        return None
    return header_get(headers, "traceparent")


def _outcome_from_mcp(result: CallToolResult) -> str:
    try:
        text = result.content[0].text  # type: ignore[union-attr]
        data = json.loads(text)
        status = data.get("status")
        if status in {"ok", "denied", "error"}:
            return str(status)
    except Exception:  # noqa: BLE001
        pass
    return "error" if result.is_error else "ok"


def build_mcp_server(runtime: Runtime) -> Server[dict[str, Any]]:
    """Low-level Server bound to runtime.invoke; serve lifespan warms ports."""
    invoke = runtime.invoke_agent_tool

    async def on_list_tools(
        ctx: ServerRequestContext[dict[str, Any], Any],
        params: PaginatedRequestParams | None,
    ) -> ListToolsResult:
        log("mcp", "tools.list")
        return ListToolsResult(tools=list_tool_specs())

    async def on_call_tool(
        ctx: ServerRequestContext[dict[str, Any], Any],
        params: CallToolRequestParams,
    ) -> CallToolResult:
        request_id = runtime.ids.new_request_id()
        tp = parse_traceparent(_traceparent_from_ctx(ctx))
        bind_context(request_id=request_id, **tp)
        tool_name = params.name
        t0 = monotonic_ms()
        log("mcp", "tools.call.start", tool=tool_name, request_id=request_id)
        try:
            bearer = _bearer_from_ctx(ctx)
            try:
                tool = ToolName(params.name)
            except ValueError:
                log("mcp", "unknown_tool", tool=tool_name, request_id=request_id)
                result = _unknown_tool(params.name)
                outcome = "error"
            else:
                handler = _HANDLERS[tool]
                args: Mapping[str, Any] = params.arguments or {}
                result = await handler(invoke, bearer, args, request_id)
                outcome = _outcome_from_mcp(result)
            duration_ms = int(monotonic_ms() - t0)
            log(
                "mcp",
                "tools.call.done",
                tool=tool_name,
                outcome=outcome,
                duration_ms=duration_ms,
                request_id=request_id,
            )
            metrics.inc("mcp_tools_call_total", tool=tool_name, outcome=outcome)
            metrics.observe_ms(
                "mcp_tools_call_duration_ms",
                float(duration_ms),
                tool=tool_name,
            )
            return result
        finally:
            clear_context()

    @asynccontextmanager
    async def lifespan(_server: Server[dict[str, Any]]) -> AsyncIterator[dict[str, Any]]:
        verifier = runtime.verifier
        database = runtime.database
        live_verifier = verifier if isinstance(verifier, LimePassportVerifier) else None
        live_db = database if isinstance(database, AsyncpgDatabaseGateway) else None
        if live_verifier is not None:
            ok = await live_verifier.warmup(raise_on_failure=True)
            status = "ok" if ok else "fail"
            log("serve", "jwks.warmup", status=status)
            metrics.inc("mcp_jwks_warmup_total", status=status)
        if live_db is not None:
            try:
                await live_db.open()
                log("serve", "pool.open", status="ok")
                metrics.inc("mcp_pool_open_total", status="ok")
            except Exception:
                log("serve", "pool.open", status="fail", level="ERROR")
                metrics.inc("mcp_pool_open_total", status="fail")
                raise
        try:
            yield {}
        finally:
            if live_db is not None:
                await live_db.close()
                log("serve", "pool.close")
            if live_verifier is not None:
                live_verifier.close()
            snap = metrics.snapshot()
            log("metrics", "metrics.summary", counters=snap.get("counters"))

    return Server(
        "lime-ref-postgres-mcp",
        lifespan=lifespan,
        on_list_tools=on_list_tools,
        on_call_tool=on_call_tool,
    )


def build_asgi_app(
    runtime: Runtime,
    *,
    disable_dns_rebinding: bool = False,
    json_response: bool = True,
    stateless_http: bool = True,
) -> tuple[Server[dict[str, Any]], Starlette]:
    """Build Server + Streamable HTTP Starlette app mounted at ``/mcp`` only."""
    server = build_mcp_server(runtime)
    if disable_dns_rebinding:
        security = TransportSecuritySettings(enable_dns_rebinding_protection=False)
    else:
        configured = os.environ.get("LIME_MCP_ALLOWED_HOSTS", "")
        allowed_hosts = [host.strip() for host in configured.split(",") if host.strip()]
        if not allowed_hosts:
            bind_host = runtime.settings.mcp_bind_host
            allowed_hosts = (
                [bind_host]
                if bind_host not in {"0.0.0.0", "::"}
                else ["127.0.0.1", "localhost", "[::1]"]
            )
        security = TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=allowed_hosts,
        )
    app = server.streamable_http_app(
        streamable_http_path=MCP_HTTP_PATH,
        json_response=json_response,
        stateless_http=stateless_http,
        host=runtime.settings.mcp_bind_host,
        transport_security=security,
    )
    return server, app


__all__ = [
    "MCP_HTTP_PATH",
    "build_asgi_app",
    "build_mcp_server",
]
