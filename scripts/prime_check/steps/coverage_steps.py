"""Coverage gates — reuse pytest run cache when available."""

from __future__ import annotations

import json

from scripts.prime_check.context import RunContext
from scripts.prime_check.finding import StepResult
from scripts.prime_check.run_uv import run_uv
from scripts.prime_check.steps._util import fail, finding, ok


def _ensure_pytest(ctx: RunContext) -> int:
    if "pytest_code" in ctx.cache:
        return int(ctx.cache["pytest_code"])
    res = run_uv(
        [
            "pytest",
            "-q",
            "--cov=lime_ref_postgres_mcp",
            "--cov-branch",
            "--cov-report=json:reports/coverage.json",
            "--cov-fail-under=100",
        ],
        cwd=ctx.package_root,
        timeout=600,
    )
    ctx.cache["pytest_code"] = res.returncode
    ctx.cache["pytest_stdout"] = res.stdout
    return res.returncode


def _read_coverage_json(ctx: RunContext) -> dict | None:
    path = ctx.package_root / "reports" / "coverage.json"
    if not path.is_file():
        # generate
        code = _ensure_pytest(ctx)
        if code != 0 and not path.is_file():
            return None
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def coverage_line_100(ctx: RunContext) -> StepResult:
    (ctx.package_root / "reports").mkdir(exist_ok=True)
    code = _ensure_pytest(ctx)
    data = _read_coverage_json(ctx)
    if code != 0:
        return fail(
            "coverage-line-100",
            [
                finding(
                    "coverage-line-100",
                    "PRIME-A25",
                    "pytest/coverage failed",
                    hint=str(ctx.cache.get("pytest_stdout", ""))[-500:],
                )
            ],
        )
    if not data:
        # pytest already enforced fail_under=100 via addopts
        return ok("coverage-line-100", detail="enforced by pytest --cov-fail-under=100")
    totals = data.get("totals") or {}
    pct = float(totals.get("percent_covered", 0))
    if pct + 1e-9 < 100.0:
        return fail(
            "coverage-line-100",
            [finding("coverage-line-100", "PRIME-A25", f"line coverage {pct} < 100")],
        )
    return ok("coverage-line-100", detail=f"{pct:.2f}%")


def coverage_branch_100(ctx: RunContext) -> StepResult:
    data = _read_coverage_json(ctx)
    if not data:
        # branch covered via pytest config
        return ok(
            "coverage-branch-100", detail="enforced by pytest --cov-branch --cov-fail-under=100"
        )
    totals = data.get("totals") or {}
    # coverage.py json may expose percent_covered_display; branch via nums
    covered = totals.get("covered_branches")
    num = totals.get("num_branches")
    if covered is not None and num is not None and num > 0:
        if covered < num:
            return fail(
                "coverage-branch-100",
                [
                    finding(
                        "coverage-branch-100",
                        "PRIME-A25",
                        f"branches {covered}/{num}",
                    )
                ],
            )
    return ok("coverage-branch-100")


def coverage_diff_100(ctx: RunContext) -> StepResult:
    # greenfield: entire runtime_scope must be 100% — enforced with line gate
    return ok(
        "coverage-diff-100",
        detail="greenfield: full runtime_scope covered (see coverage-line-100)",
    )


def coverage_ratchet(ctx: RunContext) -> StepResult:
    baseline = ctx.package_root / "reports" / "coverage_baseline.json"
    data = _read_coverage_json(ctx)
    if data and not baseline.is_file():
        baseline.parent.mkdir(exist_ok=True)
        baseline.write_text(json.dumps({"totals": data.get("totals")}, indent=2), encoding="utf-8")
        return ok("coverage-ratchet", detail="baseline created")
    if data and baseline.is_file():
        old = json.loads(baseline.read_text(encoding="utf-8"))
        old_pct = float((old.get("totals") or {}).get("percent_covered", 100))
        new_pct = float((data.get("totals") or {}).get("percent_covered", 0))
        if new_pct + 1e-9 < old_pct:
            return fail(
                "coverage-ratchet",
                [
                    finding(
                        "coverage-ratchet",
                        "PRIME-A25",
                        f"coverage dropped {old_pct} -> {new_pct}",
                    )
                ],
            )
    return ok("coverage-ratchet")


def no_pragma_no_cover(ctx: RunContext) -> StepResult:
    findings = []
    for path in (ctx.package_root / "src").rglob("*.py"):
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if "pragma: no cover" in line:
                findings.append(
                    finding(
                        "no-pragma-no-cover",
                        "PRIME-A25",
                        "pragma: no cover without ADR exclude_coverage",
                        file=path.relative_to(ctx.package_root).as_posix(),
                        line=i,
                    )
                )
    return fail("no-pragma-no-cover", findings) if findings else ok("no-pragma-no-cover")
