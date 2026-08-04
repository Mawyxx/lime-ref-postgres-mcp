"""Output / evidence step."""

from __future__ import annotations

from scripts.prime_check.context import RunContext
from scripts.prime_check.evidence import render_evidence
from scripts.prime_check.finding import Status, StepResult
from scripts.prime_check.steps._util import ok


def evidence_block(ctx: RunContext) -> StepResult:
    results: list[StepResult] = list(ctx.cache.get("all_results") or [])
    block = render_evidence(ctx.cfg, results)
    ctx.cache["evidence"] = block
    failed = [r for r in results if r.status in (Status.FAIL, Status.ERROR)]
    if failed:
        # still emit evidence content for handoff; mark FAIL
        from scripts.prime_check.steps._util import fail, finding

        return fail(
            "evidence-block",
            [
                finding(
                    "evidence-block",
                    "PRIME-A26",
                    "cannot seal evidence while other steps FAIL",
                )
            ],
            detail=block.splitlines()[0] if block else None,
        )
    return ok("evidence-block", detail="sealed")
