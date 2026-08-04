"""Step registry — LIVE callables + SKIPPED from config."""

from __future__ import annotations

from collections.abc import Callable

from scripts.prime_check.context import RunContext
from scripts.prime_check.finding import StepResult
from scripts.prime_check.steps import architecture as arch
from scripts.prime_check.steps import coverage_steps as cov
from scripts.prime_check.steps import ops, output_steps, preflight, security, static, tests_steps
from scripts.prime_check.steps._util import skipped

StepFn = Callable[[RunContext], StepResult]

# Execution order (AGENT-5)
LIVE_STEPS: list[tuple[str, StepFn]] = [
    ("stack-detect", preflight.stack_detect),
    ("config-valid", preflight.config_valid),
    ("ci-parity", preflight.ci_parity),
    ("lint", static.lint),
    ("typecheck", static.typecheck),
    ("format-check", static.format_check),
    ("dead-code-gate", static.dead_code_gate),
    ("file-size-guard", static.file_size_guard),
    ("cyclomatic-gate", static.cyclomatic_gate),
    ("import-boundaries", arch.import_boundaries),
    ("import-graph-gate", arch.import_graph_gate),
    ("deterministic-runtime", arch.deterministic_runtime),
    ("anti-null-gate", arch.anti_null_gate),
    ("immutability-gate", arch.immutability_gate),
    ("context-leak-gate", arch.context_leak_gate),
    ("error-context-gate", arch.error_context_gate),
    ("no-transport-in-domain", arch.no_transport_in_domain),
    ("di-purity", arch.di_purity),
    ("di-graph-gate", arch.di_graph_gate),
    ("handler-purity-gate", arch.handler_purity_gate),
    ("anti-fork-gate", arch.anti_fork_gate),
    ("no-string-sql", arch.no_string_sql),
    ("no-ddl-in-app", arch.no_ddl_in_app),
    ("no-secrets", security.no_secrets),
    ("bandit", security.bandit_step),
    ("dependency-audit", security.dependency_audit),
    ("sbom", security.sbom),
    ("no-debug-bypass", security.no_debug_bypass),
    ("pii-log-scan", security.pii_log_scan),
    ("pytest-unit", tests_steps.pytest_unit),
    ("pytest-integration", tests_steps.pytest_integration),
    ("pytest-contract", tests_steps.pytest_contract),
    ("pytest-e2e", tests_steps.pytest_e2e),
    ("injection-fuzz", security.injection_fuzz),
    ("zta-matrix-gate", security.zta_matrix_gate),
    ("route-matrix-gate", tests_steps.route_matrix_gate),
    ("e2e-only-anti-pattern", tests_steps.e2e_only_anti_pattern),
    ("no-empty-test", tests_steps.no_empty_test),
    ("no-trivial-assert", tests_steps.no_trivial_assert),
    ("err-variant-gate", tests_steps.err_variant_gate),
    ("test-matrix-gate", tests_steps.test_matrix_gate),
    ("regression-lock", tests_steps.regression_lock),
    ("coverage-line-100", cov.coverage_line_100),
    ("coverage-branch-100", cov.coverage_branch_100),
    ("coverage-diff-100", cov.coverage_diff_100),
    ("coverage-ratchet", cov.coverage_ratchet),
    ("no-pragma-no-cover", cov.no_pragma_no_cover),
    ("prod-config", ops.prod_config),
    ("evidence-block", output_steps.evidence_block),
]


def all_step_ids(skipped_keys: dict[str, dict[str, str]]) -> list[str]:
    live_ids = [s for s, _ in LIVE_STEPS]
    skip_ids = sorted(skipped_keys.keys())
    # unique preserve order: live then skips not already live
    out = list(live_ids)
    for s in skip_ids:
        if s not in out:
            out.append(s)
    return out


def resolve_steps(
    skipped_keys: dict[str, dict[str, str]],
) -> list[tuple[str, StepFn]]:
    live_map = dict(LIVE_STEPS)
    ordered = all_step_ids(skipped_keys)
    resolved: list[tuple[str, StepFn]] = []
    for step_id in ordered:
        if step_id in skipped_keys:
            meta = skipped_keys[step_id]
            adr = meta.get("adr", "ADR-002")
            flip = meta.get("flip_phase", "?")

            def make_skip(sid: str = step_id, a: str = adr, f: str = flip) -> StepFn:
                return lambda ctx: skipped(sid, a, f)

            resolved.append((step_id, make_skip()))
        elif step_id in live_map:
            resolved.append((step_id, live_map[step_id]))
    return resolved
