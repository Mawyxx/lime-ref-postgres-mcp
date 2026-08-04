"""Preflight steps."""

from __future__ import annotations

import re
import sys

from scripts.prime_check.context import RunContext
from scripts.prime_check.finding import StepResult
from scripts.prime_check.steps._util import fail, finding, ok


def stack_detect(ctx: RunContext) -> StepResult:
    if sys.version_info < (3, 12):
        return fail(
            "stack-detect",
            [finding("stack-detect", "PRIME-A22", f"Python >=3.12 required, got {sys.version}")],
        )
    return ok("stack-detect", detail=f"python {sys.version_info.major}.{sys.version_info.minor}")


def config_valid(ctx: RunContext) -> StepResult:
    # load already validated; re-check critical fields
    arch = ctx.cfg.architecture
    for key in ("core_scope", "application_scope", "testable_core_scope"):
        if key not in arch:
            return fail(
                "config-valid",
                [finding("config-valid", "PRIME-A22", f"architecture missing {key}")],
            )
    return ok("config-valid")


def ci_parity(ctx: RunContext) -> StepResult:
    rel = ctx.cfg.ci.get("workflow_path", "")
    expected = ctx.cfg.ci.get("expected_run", "")
    path = ctx.package_root / rel
    if not path.is_file():
        return fail(
            "ci-parity",
            [
                finding(
                    "ci-parity",
                    "PRIME-A22",
                    f"workflow missing: {rel}",
                    hint="add package-local .github/workflows/prime_check.yml",
                )
            ],
        )
    text = path.read_text(encoding="utf-8")
    # Normalize whitespace for multi-line run blocks
    if expected not in text:
        return fail(
            "ci-parity",
            [
                finding(
                    "ci-parity",
                    "PRIME-A22",
                    f"workflow must contain exact run: {expected!r}",
                    file=rel,
                    hint="local ≡ CI command",
                )
            ],
        )
    # Prefer a run: line match
    if not re.search(rf"run:\s*[|\"]?\s*{re.escape(expected)}", text) and expected not in text:
        return fail(
            "ci-parity",
            [
                finding(
                    "ci-parity", "PRIME-A22", "ci expected_run not found as run command", file=rel
                )
            ],
        )
    return ok("ci-parity", detail=expected)
