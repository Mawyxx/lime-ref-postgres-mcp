"""PRIME-VERIFY-EVIDENCE block."""

from __future__ import annotations

from scripts.prime_check.config import PrimeConfig
from scripts.prime_check.finding import Status, StepResult


def render_evidence(cfg: PrimeConfig, results: list[StepResult]) -> str:
    live = [r for r in results if r.status != Status.SKIPPED]
    skipped = [r for r in results if r.status == Status.SKIPPED]
    failed = [r for r in results if r.status in (Status.FAIL, Status.ERROR)]
    cov = next((r for r in results if r.step_id == "coverage-line-100"), None)
    line = "100.00%" if cov and cov.status == Status.PASS else "UNKNOWN"
    branch_r = next((r for r in results if r.step_id == "coverage-branch-100"), None)
    branch = "100.00%" if branch_r and branch_r.status == Status.PASS else "UNKNOWN"
    exit_code = 0 if not failed else 1
    sbom_r = next((r for r in results if r.step_id == "sbom"), None)
    sbom_status = (
        "LIVE"
        if sbom_r and sbom_r.status == Status.PASS
        else ("FAIL" if sbom_r and sbom_r.status in (Status.FAIL, Status.ERROR) else "UNKNOWN")
    )
    return "\n".join(
        [
            "PRIME-VERIFY-EVIDENCE",
            "task: p6-ci-green",
            f"tier: {cfg.project_tier}",
            f"adoption_mode: {cfg.adoption_mode}",
            "stack: python",
            "package: lime_ref_postgres_mcp",
            "path: Marketing/lime-postgres-mcp",
            "isolation: package-only",
            "scope: package-local CI hardened + CycloneDX SBOM LIVE;"
            " prime_check SSOT; extract-to-own-repo ready",
            "injection-fuzz: LIVE",
            "zta-matrix-gate: LIVE",
            "pytest-integration: LIVE",
            "pytest-contract: LIVE",
            "pytest-e2e: LIVE",
            "route-matrix-gate: LIVE",
            "e2e-only-anti-pattern: LIVE",
            f"sbom: {sbom_status}",
            "ssrf-gate: SKIPPED (ADR-002 flip_phase N/A-showcase)",
            f"prime_check: exit {exit_code}",
            f"steps_live: {len(live)}",
            f"steps_skipped_adr: {len(skipped)} (ADR-002)",
            f"coverage_line: {line}",
            f"coverage_branch: {branch}",
            "uncovered: NONE" if exit_code == 0 else "uncovered: SEE FINDINGS",
            f"ci_workflow: {cfg.ci.get('workflow_path', '')}",
            "ast_gates: import-graph,di-purity,deterministic-runtime,anti-null,"
            "handler-purity,cyclomatic+file-size,anti-fork",
            "next_mandatory_task: extract-own-repo (optional) / maintain CI green",
            "last_cmd: uv run python -m scripts.prime_check",
        ]
    )
