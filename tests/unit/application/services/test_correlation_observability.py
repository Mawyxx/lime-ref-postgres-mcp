"""Correlation: request_id on process path + agent event meta."""

from __future__ import annotations

import io
import json

import pytest
from tests.support.build_test_runtime import wire_invoke

from lime_ref_postgres_mcp.application.commands.invoke_agent_tool import InvokeAgentToolCommand
from lime_ref_postgres_mcp.bootstrap.observability.configure import (
    configure_observability,
    reset_configure_for_tests,
)
from lime_ref_postgres_mcp.bootstrap.observability.metrics import metrics
from lime_ref_postgres_mcp.domain.catalog.tool_catalog import ToolName
from lime_ref_postgres_mcp.domain.common.result import Ok


@pytest.fixture(autouse=True)
def _obs_buf() -> io.StringIO:
    reset_configure_for_tests()
    buf = io.StringIO()
    configure_observability(level="DEBUG", format="json", stream=buf, metrics_enabled=True)
    metrics.reset(enabled=True)
    yield buf
    reset_configure_for_tests()


@pytest.mark.asyncio
async def test_ok_path_request_id_matches_event() -> None:
    invoke, bus = wire_invoke()
    result = await invoke.execute(
        InvokeAgentToolCommand(
            bearer_token="tok",
            tool=ToolName.LIST_SCHEMAS,
            args={},
            request_id="req-corr-1",
        )
    )
    assert isinstance(result, Ok)
    assert bus.events
    assert bus.events[0].meta.get("request_id") == "req-corr-1"


@pytest.mark.asyncio
async def test_preauth_logs_metric_and_no_event(_obs_buf: io.StringIO) -> None:
    from lime_ref_postgres_mcp.domain.common.result import Err

    invoke, bus = wire_invoke()
    result = await invoke.execute(
        InvokeAgentToolCommand(
            bearer_token=None,
            tool=ToolName.LIST_SCHEMAS,
            args={},
            request_id="req-preauth",
        )
    )
    assert isinstance(result, Err)
    assert bus.events == []
    lines = [json.loads(ln) for ln in _obs_buf.getvalue().splitlines() if ln.strip()]
    assert any(r.get("event") == "preauth.fail" for r in lines)
    snap = metrics.snapshot()["counters"]
    assert any(k.startswith("mcp_preauth_fail_total") for k in snap)
