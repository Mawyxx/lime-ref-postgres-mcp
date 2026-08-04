"""Thin e2e Streamable HTTP smoke with fakes (no live JWKS/Postgres)."""

from __future__ import annotations

import json
import threading

import httpx
import pytest
import uvicorn
from tests.support.build_test_runtime import build_test_runtime

from lime_ref_postgres_mcp.bootstrap.settings import Settings
from lime_ref_postgres_mcp.presentation.mcp.server import MCP_HTTP_PATH, build_asgi_app


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_streamable_http_loopback_smoke(settings: Settings) -> None:
    tr = build_test_runtime(settings)
    server, app = build_asgi_app(tr.runtime, disable_dns_rebinding=True)
    config = uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning")
    uvi = uvicorn.Server(config)

    thread = threading.Thread(target=uvi.run, daemon=True)
    # Enter session manager in the uvicorn lifespan — streamable_http_app already
    # sets lifespan=session_manager.run, so starting uvicorn is enough.
    thread.start()
    # wait until started
    for _ in range(100):
        if uvi.started:
            break
        await _sleep(0.05)
    assert uvi.started
    port = _bound_port(uvi)
    base = f"http://127.0.0.1:{port}"
    headers = {
        "Authorization": "Bearer tok",
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(base_url=base, timeout=10.0) as client:
            init = await client.post(
                MCP_HTTP_PATH,
                headers=headers,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-03-26",
                        "capabilities": {},
                        "clientInfo": {"name": "e2e", "version": "0"},
                    },
                },
            )
            assert init.status_code == 200, init.text
            await client.post(
                MCP_HTTP_PATH,
                headers=headers,
                json={"jsonrpc": "2.0", "method": "notifications/initialized"},
            )
            call = await client.post(
                MCP_HTTP_PATH,
                headers=headers,
                json={
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {"name": "list_schemas", "arguments": {}},
                },
            )
            assert call.status_code == 200, call.text
            payload = call.json()["result"]
            assert payload["isError"] is False
            envelope = json.loads(payload["content"][0]["text"])
            assert envelope["status"] == "ok"
            assert tr.bus.events
    finally:
        uvi.should_exit = True
        thread.join(timeout=5)


async def _sleep(seconds: float) -> None:
    import asyncio

    await asyncio.sleep(seconds)


def _bound_port(server: uvicorn.Server) -> int:
    sockets = server.servers[0].sockets if server.servers else []
    assert sockets, "uvicorn did not bind a socket"
    return int(sockets[0].getsockname()[1])
