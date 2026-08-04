"""Collect-all orchestrator."""

from __future__ import annotations

import time

from scripts.prime_check.config import PrimeConfig
from scripts.prime_check.context import RunContext
from scripts.prime_check.finding import Status, StepResult
from scripts.prime_check.registry import resolve_steps


def run_all(
    cfg: PrimeConfig,
    *,
    only: set[str] | None = None,
) -> list[StepResult]:
    ctx = RunContext(cfg=cfg, package_root=cfg.package_root, only=only)
    steps = resolve_steps(cfg.skipped_steps)
    results: list[StepResult] = []
    for step_id, fn in steps:
        if only is not None and step_id not in only:
            continue
        # Keep rolling results for evidence-block
        ctx.cache["all_results"] = list(results)
        start = time.perf_counter()
        try:
            result = fn(ctx)
        except Exception as exc:  # noqa: BLE001 — gate must not crash run
            result = StepResult(
                step_id=step_id,
                status=Status.ERROR,
                duration_ms=0,
                detail=str(exc),
            )
        if result.duration_ms == 0:
            result.duration_ms = int((time.perf_counter() - start) * 1000)
        result.step_id = step_id
        results.append(result)
        ctx.cache["all_results"] = list(results)
    return results


def exit_code(results: list[StepResult]) -> int:
    if any(r.status in (Status.FAIL, Status.ERROR) for r in results):
        return 1
    return 0
