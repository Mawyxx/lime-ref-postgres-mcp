"""Step helpers."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar

from scripts.prime_check.context import RunContext
from scripts.prime_check.finding import Finding, Status, StepResult

F = TypeVar("F", bound=Callable[[RunContext], StepResult])


def timed(
    step_id: str, fn: Callable[[RunContext], StepResult]
) -> Callable[[RunContext], StepResult]:
    def wrapper(ctx: RunContext) -> StepResult:
        start = time.perf_counter()
        result = fn(ctx)
        result.duration_ms = int((time.perf_counter() - start) * 1000)
        result.step_id = step_id
        return result

    return wrapper


def ok(step_id: str, detail: str | None = None) -> StepResult:
    return StepResult(step_id=step_id, status=Status.PASS, duration_ms=0, detail=detail)


def fail(step_id: str, findings: list[Finding], detail: str | None = None) -> StepResult:
    return StepResult(
        step_id=step_id,
        status=Status.FAIL,
        duration_ms=0,
        findings=findings,
        detail=detail,
    )


def skipped(step_id: str, adr: str, flip: str) -> StepResult:
    return StepResult(
        step_id=step_id,
        status=Status.SKIPPED,
        duration_ms=0,
        skip_adr=adr,
        detail=f"flip_phase={flip}",
    )


def finding(
    step: str,
    rule_id: str,
    issue: str,
    *,
    file: str | None = None,
    line: int | None = None,
    hint: str | None = None,
    priority: str = "P1",
) -> Finding:
    return Finding(
        rule_id=rule_id,
        step=step,
        priority=priority,
        issue=issue,
        file=file,
        line=line,
        hint=hint,
        rerun=f"uv run python -m scripts.prime_check --only {step}",
    )
