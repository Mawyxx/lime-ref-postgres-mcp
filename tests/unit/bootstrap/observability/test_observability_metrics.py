"""ProcessMetrics unit tests."""

from __future__ import annotations

from lime_ref_postgres_mcp.bootstrap.observability.metrics import ProcessMetrics


def test_inc_and_observe_snapshot() -> None:
    m = ProcessMetrics()
    m.inc("mcp_tools_call_total", tool="select_rows", outcome="ok")
    m.inc("mcp_tools_call_total", tool="select_rows", outcome="ok")
    m.observe_ms("mcp_db_op_duration_ms", 12.0, op="select_rows")
    snap = m.snapshot()
    assert snap["counters"]["mcp_tools_call_total|outcome=ok,tool=select_rows"] == 2
    hist = snap["histograms"]["mcp_db_op_duration_ms|op=select_rows"]
    assert isinstance(hist, dict)
    assert hist["25"] == 1


def test_metrics_disabled_noop() -> None:
    m = ProcessMetrics()
    m.set_enabled(False)
    m.inc("x")
    m.observe_ms("y", 1.0)
    assert m.snapshot()["counters"] == {}
    assert m.snapshot()["histograms"] == {}


def test_observe_overflow_bucket() -> None:
    m = ProcessMetrics()
    m.observe_ms("mcp_db_op_duration_ms", 9000.0, op="x")
    hist = m.snapshot()["histograms"]["mcp_db_op_duration_ms|op=x"]
    assert hist["inf"] == 1
