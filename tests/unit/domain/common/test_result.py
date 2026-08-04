"""Result algebra unit tests."""

from __future__ import annotations

import pytest

from lime_ref_postgres_mcp.domain.common.result import Err, Ok, is_err, is_ok, unwrap, unwrap_err


def test_ok_helpers() -> None:
    result: Ok[int] | Err[str] = Ok(42)
    assert is_ok(result) is True
    assert is_err(result) is False
    assert unwrap(result) == 42


def test_err_helpers() -> None:
    result: Ok[int] | Err[str] = Err("boom")
    assert is_ok(result) is False
    assert is_err(result) is True
    assert unwrap_err(result) == "boom"


def test_unwrap_on_err_raises() -> None:
    result: Ok[int] | Err[str] = Err("nope")
    with pytest.raises(ValueError, match="unwrap called on Err"):
        unwrap(result)


def test_unwrap_err_on_ok_raises() -> None:
    result: Ok[int] | Err[str] = Ok(1)
    with pytest.raises(ValueError, match="unwrap_err called on Ok"):
        unwrap_err(result)
