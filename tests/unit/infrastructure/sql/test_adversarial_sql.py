"""Adversarial SQL analyzer tests (Adv-1..10, Adv-P)."""

from __future__ import annotations

import pytest
from tests.unit.infrastructure.sql.adversarial_cases import ADVERSARIAL_CASES, AdversarialCase

from lime_ref_postgres_mcp.domain.common.result import Err, Ok, unwrap, unwrap_err
from lime_ref_postgres_mcp.infrastructure.sql.pglast_sql_analyzer import PglastSqlAnalyzer


@pytest.fixture
def analyzer() -> PglastSqlAnalyzer:
    return PglastSqlAnalyzer()


@pytest.mark.parametrize("case", ADVERSARIAL_CASES, ids=[c.id for c in ADVERSARIAL_CASES])
def test_adversarial_analyzer(case: AdversarialCase, analyzer: PglastSqlAnalyzer) -> None:
    result = analyzer.analyze(case.sql)
    if case.expect_err:
        assert isinstance(result, Err)
        return
    assert isinstance(result, Ok)
    analysis = unwrap(result)
    assert analysis.statement_class == case.expect_class
    if case.expect_top_level is not None:
        assert analysis.top_level_kind == case.expect_top_level
    if case.expect_modifying_cte is not None:
        assert analysis.has_modifying_cte == case.expect_modifying_cte
    if case.expect_explain_analyze is not None:
        assert analysis.is_explain_analyze == case.expect_explain_analyze


def test_adv_p_parse_fault_type(analyzer: PglastSqlAnalyzer) -> None:
    assert isinstance(unwrap_err(analyzer.analyze("SELEC 1")), Exception)
