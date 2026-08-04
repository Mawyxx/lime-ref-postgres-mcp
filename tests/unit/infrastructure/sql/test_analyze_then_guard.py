"""analyze → guard pipeline tests (Pipe-1..10)."""

from __future__ import annotations

import pytest
from tests.unit.infrastructure.sql.adversarial_cases import ADVERSARIAL_CASES, AdversarialCase

from lime_ref_postgres_mcp.domain.access.capability import ToolCapability
from lime_ref_postgres_mcp.domain.catalog.tool_catalog import ToolName
from lime_ref_postgres_mcp.domain.common.result import Err, unwrap
from lime_ref_postgres_mcp.domain.sql.guard import guard
from lime_ref_postgres_mcp.infrastructure.sql.pglast_sql_analyzer import PglastSqlAnalyzer

READ_PERMS = frozenset({ToolCapability.READ_DATA, ToolCapability.READ_SCHEMA})
WRITE_PERMS = frozenset(
    {ToolCapability.READ_DATA, ToolCapability.READ_SCHEMA, ToolCapability.WRITE_DATA}
)


@pytest.fixture
def analyzer() -> PglastSqlAnalyzer:
    return PglastSqlAnalyzer()


def _run_guard(
    case: AdversarialCase,
    tool: ToolName,
    perms: frozenset[ToolCapability],
    analyzer: PglastSqlAnalyzer,
) -> bool:
    result = analyzer.analyze(case.sql)
    if case.expect_err:
        assert isinstance(result, Err)
        return False
    analysis = unwrap(result)
    decision = guard(tool, analysis, perms)
    return decision.allowed


@pytest.mark.parametrize(
    "case", [c for c in ADVERSARIAL_CASES if not c.expect_err], ids=lambda c: c.id
)
def test_pipeline_readonly(case: AdversarialCase, analyzer: PglastSqlAnalyzer) -> None:
    allowed = _run_guard(case, ToolName.EXECUTE_READONLY_QUERY, READ_PERMS, analyzer)
    assert allowed is False


@pytest.mark.parametrize(
    "case", [c for c in ADVERSARIAL_CASES if not c.expect_err], ids=lambda c: c.id
)
def test_pipeline_explain(case: AdversarialCase, analyzer: PglastSqlAnalyzer) -> None:
    allowed = _run_guard(case, ToolName.EXPLAIN_QUERY_PLAN, READ_PERMS, analyzer)
    assert allowed is False


@pytest.mark.parametrize("case", ADVERSARIAL_CASES, ids=[c.id for c in ADVERSARIAL_CASES])
def test_pipeline_write(case: AdversarialCase, analyzer: PglastSqlAnalyzer) -> None:
    if case.expect_err:
        result = analyzer.analyze(case.sql)
        assert isinstance(result, Err)
        return
    analysis = unwrap(analyzer.analyze(case.sql))
    allowed = guard(ToolName.EXECUTE_WRITE_QUERY, analysis, WRITE_PERMS).allowed
    assert allowed is case.guard_write
