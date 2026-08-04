"""Static analysis steps via uv tools + ast size/complexity."""

from __future__ import annotations

import ast

from scripts.prime_check.astlib import iter_py_files, mccabe_complexity, parse_module
from scripts.prime_check.context import RunContext
from scripts.prime_check.finding import StepResult
from scripts.prime_check.run_uv import run_uv
from scripts.prime_check.steps._util import fail, finding, ok


def lint(ctx: RunContext) -> StepResult:
    res = run_uv(["ruff", "check", "src", "tests"], cwd=ctx.package_root)
    if res.returncode != 0:
        return fail(
            "lint",
            [
                finding(
                    "lint",
                    "PRIME-A17",
                    "ruff check failed",
                    hint=(res.stdout or res.stderr)[:500],
                )
            ],
        )
    return ok("lint")


def typecheck(ctx: RunContext) -> StepResult:
    res = run_uv(["mypy", "src"], cwd=ctx.package_root)
    if res.returncode != 0:
        return fail(
            "typecheck",
            [
                finding(
                    "typecheck",
                    "PRIME-A17",
                    "mypy failed",
                    hint=(res.stdout or res.stderr)[:500],
                )
            ],
        )
    return ok("typecheck")


def format_check(ctx: RunContext) -> StepResult:
    res = run_uv(["ruff", "format", "--check", "src", "tests"], cwd=ctx.package_root)
    if res.returncode != 0:
        return fail(
            "format-check",
            [
                finding(
                    "format-check",
                    "PRIME-A17",
                    "ruff format --check failed",
                    hint=(res.stdout or res.stderr)[:500],
                )
            ],
        )
    return ok("format-check")


def dead_code_gate(ctx: RunContext) -> StepResult:
    res = run_uv(
        ["vulture", "src/lime_ref_postgres_mcp", "--min-confidence", "80"],
        cwd=ctx.package_root,
    )
    # vulture exit 0 even with findings sometimes; parse stdout
    out = (res.stdout or "").strip()
    if out:
        # Allow unused in empty marker packages / Protocol ellipsis noise — fail only high-signal
        lines = [ln for ln in out.splitlines() if ln.strip()]
        # Filter known empty-package noise
        noise = ("__init__.py",)
        real = [ln for ln in lines if not any(n in ln for n in noise)]
        if real:
            return fail(
                "dead-code-gate",
                [
                    finding(
                        "dead-code-gate",
                        "PRIME-A11",
                        "vulture reported unused code",
                        hint="\n".join(real[:20]),
                    )
                ],
            )
    return ok("dead-code-gate")


def file_size_guard(ctx: RunContext) -> StepResult:
    max_lines = int(ctx.cfg.architecture.get("file_max_lines", 300))
    findings = []
    for path in iter_py_files(ctx.package_root, ctx.cfg.runtime_scope):
        n = len(path.read_text(encoding="utf-8").splitlines())
        if n > max_lines:
            findings.append(
                finding(
                    "file-size-guard",
                    "PRIME-A11",
                    f"{n} lines > {max_lines}",
                    file=path.relative_to(ctx.package_root).as_posix(),
                )
            )
    return fail("file-size-guard", findings) if findings else ok("file-size-guard")


def cyclomatic_gate(ctx: RunContext) -> StepResult:
    max_c = int(ctx.cfg.architecture.get("cyclomatic_max", 10))
    findings = []
    for path in iter_py_files(ctx.package_root, ctx.cfg.runtime_scope):
        mod = parse_module(path, ctx.package_root)
        for node in ast.walk(mod.tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                c = mccabe_complexity(node)
                if c > max_c:
                    findings.append(
                        finding(
                            "cyclomatic-gate",
                            "PRIME-A11",
                            f"{node.name} complexity {c} > {max_c}",
                            file=mod.rel,
                            line=getattr(node, "lineno", None),
                            hint="split function",
                        )
                    )
    return fail("cyclomatic-gate", findings) if findings else ok("cyclomatic-gate")
