"""Test pyramid gates."""

from __future__ import annotations

import ast
import re

from scripts.prime_check.context import RunContext
from scripts.prime_check.finding import StepResult
from scripts.prime_check.run_uv import run_uv
from scripts.prime_check.steps._util import fail, finding, ok

P2_MATRIX = [
    ("Result Ok/Err", "tests/unit/domain/common/test_result.py"),
    ("DomainError", "tests/unit/domain/common/test_errors.py"),
    ("AgentId", "tests/unit/domain/agent/test_agent_id.py"),
    ("Policy resolve", "tests/unit/domain/access/test_policy.py"),
    ("Capability check", "tests/unit/domain/access/test_capability_check.py"),
    ("Tool catalog", "tests/unit/domain/catalog/test_tool_catalog.py"),
    ("SQL analysis", "tests/unit/domain/sql/test_sql_analysis.py"),
    ("SQL guard", "tests/unit/domain/sql/test_guard.py"),
    ("AgentActionEvent", "tests/unit/domain/auditing/test_agent_action_event.py"),
    ("SqlAnalyzer port", "tests/unit/application/ports/test_sql_analyzer_port.py"),
    ("PglastSqlAnalyzer", "tests/unit/infrastructure/sql/test_pglast_sql_analyzer.py"),
    ("Adversarial SQL", "tests/unit/infrastructure/sql/test_adversarial_sql.py"),
    ("analyze->guard pipeline", "tests/unit/infrastructure/sql/test_analyze_then_guard.py"),
    (
        "EstablishRequestContext",
        "tests/unit/application/services/test_establish_request_context.py",
    ),
    ("AuthorizeTool", "tests/unit/application/services/test_authorize_tool.py"),
    ("EmitAgentAction", "tests/unit/application/services/test_emit_agent_action.py"),
    ("InvokeAgentTool", "tests/unit/application/services/test_invoke_agent_tool.py"),
    ("ZTA matrix", "tests/contract/test_zta_matrix.py"),
    ("InProcessEventBus", "tests/unit/infrastructure/events/test_in_process_event_bus.py"),
    ("JsonAgentPolicyStore", "tests/unit/infrastructure/policy/test_json_agent_policy_store.py"),
    (
        "LimePassportVerifier",
        "tests/unit/infrastructure/identity/test_lime_passport_verifier.py",
    ),
    ("domain_normalize", "tests/unit/infrastructure/identity/test_domain_normalize.py"),
    ("Settings", "tests/unit/bootstrap/test_settings.py"),
    ("Runtime/container", "tests/unit/bootstrap/test_container.py"),
    ("Clock adapters", "tests/unit/infrastructure/clock/test_clock_adapters.py"),
    ("__main__", "tests/unit/test_main.py"),
    ("import-law", "tests/architecture/test_import_graph.py"),
]

P3_MATRIX = P2_MATRIX

P4_MATRIX = [
    *P3_MATRIX,
    (
        "AsyncpgDatabaseGateway",
        "tests/unit/infrastructure/postgres/test_asyncpg_database_gateway.py",
    ),
    ("asyncpg pool", "tests/unit/infrastructure/postgres/test_pool.py"),
    ("Postgres integration", "tests/integration/test_postgres_gateway.py"),
]

P5_MATRIX = [
    *P4_MATRIX,
    ("MCP auth", "tests/unit/presentation/mcp/test_auth.py"),
    ("MCP error_map", "tests/unit/presentation/mcp/test_error_map.py"),
    ("MCP tool_specs", "tests/unit/presentation/mcp/test_tool_specs.py"),
    ("MCP handlers", "tests/unit/presentation/mcp/test_handlers.py"),
    ("MCP server", "tests/unit/presentation/mcp/test_server.py"),
    ("ConsoleSink", "tests/unit/subscribers/test_console_sink.py"),
    ("MCP HTTP contract", "tests/contract/test_mcp_http.py"),
    ("MCP e2e Streamable HTTP", "tests/e2e/test_mcp_streamable_http.py"),
]


def pytest_unit(ctx: RunContext) -> StepResult:
    (ctx.package_root / "reports").mkdir(exist_ok=True)
    res = run_uv(
        [
            "pytest",
            "-q",
            "-m",
            "not integration and not e2e",
            "--cov=lime_ref_postgres_mcp",
            "--cov-branch",
            "--cov-report=json:reports/coverage.json",
            "--cov-fail-under=100",
        ],
        cwd=ctx.package_root,
        timeout=600,
    )
    ctx.cache["pytest_stdout"] = res.stdout
    ctx.cache["pytest_stderr"] = res.stderr
    ctx.cache["pytest_code"] = res.returncode
    if res.returncode != 0:
        return fail(
            "pytest-unit",
            [
                finding(
                    "pytest-unit",
                    "PRIME-A12",
                    "pytest failed",
                    hint=(res.stdout or res.stderr)[-800:],
                )
            ],
        )
    return ok("pytest-unit")


def pytest_integration(ctx: RunContext) -> StepResult:
    res = run_uv(
        [
            "pytest",
            "tests/integration",
            "-q",
            "-m",
            "integration",
            "--no-cov",
            "-o",
            "addopts=",
        ],
        cwd=ctx.package_root,
        timeout=600,
    )
    if res.returncode != 0:
        return fail(
            "pytest-integration",
            [
                finding(
                    "pytest-integration",
                    "PRIME-A12",
                    "integration pytest failed",
                    hint=(res.stdout or res.stderr)[-800:],
                )
            ],
        )
    combined = (res.stdout or "") + (res.stderr or "")
    if "collected 0 items" in combined or "no tests ran" in combined.lower():
        return fail(
            "pytest-integration",
            [
                finding(
                    "pytest-integration",
                    "PRIME-A12",
                    "no integration tests collected",
                    hint=combined[-400:],
                )
            ],
        )
    return ok("pytest-integration")


def no_empty_test(ctx: RunContext) -> StepResult:
    findings = []
    tests_root = ctx.package_root / "tests"
    for path in tests_root.rglob("test_*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith(
                "test_"
            ):
                body = [
                    s
                    for s in node.body
                    if not (
                        isinstance(s, ast.Expr)
                        and isinstance(s.value, ast.Constant)
                        and isinstance(s.value.value, str)
                    )
                ]
                if not body:
                    findings.append(
                        finding(
                            "no-empty-test",
                            "PRIME-A27",
                            f"empty test {node.name}",
                            file=path.relative_to(ctx.package_root).as_posix(),
                            line=node.lineno,
                        )
                    )
                # pass-only
                if len(body) == 1 and isinstance(body[0], ast.Pass):
                    findings.append(
                        finding(
                            "no-empty-test",
                            "PRIME-A27",
                            f"pass-only test {node.name}",
                            file=path.relative_to(ctx.package_root).as_posix(),
                            line=node.lineno,
                        )
                    )
    return fail("no-empty-test", findings) if findings else ok("no-empty-test")


def no_trivial_assert(ctx: RunContext) -> StepResult:
    findings = []
    for path in (ctx.package_root / "tests").rglob("test_*.py"):
        text = path.read_text(encoding="utf-8")
        for i, line in enumerate(text.splitlines(), 1):
            if re.search(r"assert\s+True\b", line) or re.search(r"assert\s+1\s*==\s*1", line):
                findings.append(
                    finding(
                        "no-trivial-assert",
                        "PRIME-A27",
                        "trivial assert",
                        file=path.relative_to(ctx.package_root).as_posix(),
                        line=i,
                    )
                )
    return fail("no-trivial-assert", findings) if findings else ok("no-trivial-assert")


def err_variant_gate(ctx: RunContext) -> StepResult:
    required = {
        "DomainError": "tests/unit/domain/common/test_errors.py",
        "InvariantViolation": "tests/unit/domain/common/test_errors.py",
        "AgentNotAllowlisted": "tests/unit/domain/common/test_errors.py",
        "CapabilityDenied": "tests/unit/domain/common/test_errors.py",
        "StatementClassDenied": "tests/unit/domain/common/test_errors.py",
        "ToolInputInvalid": "tests/unit/domain/common/test_errors.py",
        "PassportMissing": "tests/unit/domain/common/test_errors.py",
        "PassportInvalid": "tests/unit/domain/common/test_errors.py",
        "DatabaseFault": "tests/unit/domain/common/test_errors.py",
        "PolicyStoreFault": "tests/unit/domain/common/test_errors.py",
        "SqlParseFault": "tests/unit/domain/common/test_errors.py",
        "ConfigurationError": "tests/unit/bootstrap/test_settings.py",
    }
    findings = []
    for name, rel in required.items():
        path = ctx.package_root / rel
        if not path.is_file() or name not in path.read_text(encoding="utf-8"):
            findings.append(
                finding(
                    "err-variant-gate",
                    "PRIME-A10",
                    f"missing dedicated tests for {name}",
                    file=rel,
                )
            )
    return fail("err-variant-gate", findings) if findings else ok("err-variant-gate")


def test_matrix_gate(ctx: RunContext) -> StepResult:
    findings = []
    for label, rel in P5_MATRIX:
        if not (ctx.package_root / rel).is_file():
            findings.append(
                finding(
                    "test-matrix-gate",
                    "PRIME-A12",
                    f"missing matrix cell {label}",
                    file=rel,
                )
            )
    return fail("test-matrix-gate", findings) if findings else ok("test-matrix-gate")


def regression_lock(ctx: RunContext) -> StepResult:
    # No bugfix inventory yet — PASS with detail
    return ok("regression-lock", detail="no regression inventory yet")


def pytest_contract(ctx: RunContext) -> StepResult:
    res = run_uv(
        [
            "pytest",
            "tests/contract",
            "-q",
            "--no-cov",
            "-o",
            "addopts=",
        ],
        cwd=ctx.package_root,
        timeout=600,
    )
    if res.returncode != 0:
        return fail(
            "pytest-contract",
            [
                finding(
                    "pytest-contract",
                    "PRIME-A12",
                    "contract pytest failed",
                    hint=(res.stdout or res.stderr)[-800:],
                )
            ],
        )
    return ok("pytest-contract")


def pytest_e2e(ctx: RunContext) -> StepResult:
    res = run_uv(
        [
            "pytest",
            "tests/e2e",
            "-q",
            "-m",
            "e2e",
            "--no-cov",
            "-o",
            "addopts=",
        ],
        cwd=ctx.package_root,
        timeout=600,
    )
    if res.returncode != 0:
        return fail(
            "pytest-e2e",
            [
                finding(
                    "pytest-e2e",
                    "PRIME-A12",
                    "e2e pytest failed",
                    hint=(res.stdout or res.stderr)[-800:],
                )
            ],
        )
    combined = (res.stdout or "") + (res.stderr or "")
    if "collected 0 items" in combined or "no tests ran" in combined.lower():
        return fail(
            "pytest-e2e",
            [
                finding(
                    "pytest-e2e",
                    "PRIME-A12",
                    "no e2e tests collected",
                    hint=combined[-400:],
                )
            ],
        )
    return ok("pytest-e2e")


def route_matrix_gate(ctx: RunContext) -> StepResult:
    """Only `/mcp` Streamable HTTP; exactly 8 ToolNames; no REST/health/stdio."""
    findings = []
    server_py = (
        ctx.package_root / "src" / "lime_ref_postgres_mcp" / "presentation" / "mcp" / "server.py"
    )
    specs_py = (
        ctx.package_root
        / "src"
        / "lime_ref_postgres_mcp"
        / "presentation"
        / "mcp"
        / "tool_specs.py"
    )
    catalog_py = (
        ctx.package_root
        / "src"
        / "lime_ref_postgres_mcp"
        / "domain"
        / "catalog"
        / "tool_catalog.py"
    )
    if not server_py.is_file():
        findings.append(
            finding("route-matrix-gate", "PRIME-A05", "missing presentation/mcp/server.py")
        )
        return fail("route-matrix-gate", findings)
    server_src = server_py.read_text(encoding="utf-8")
    if 'MCP_HTTP_PATH = "/mcp"' not in server_src and "MCP_HTTP_PATH='/mcp'" not in server_src:
        findings.append(
            finding(
                "route-matrix-gate",
                "PRIME-A05",
                "MCP_HTTP_PATH must be /mcp",
                file=server_py.relative_to(ctx.package_root).as_posix(),
            )
        )
    for banned in ("/health", "stdio", "FastAPI", "@app.get", "@app.post"):
        if banned in server_src:
            findings.append(
                finding(
                    "route-matrix-gate",
                    "PRIME-A05",
                    f"forbidden surface token {banned!r} in server.py",
                    file=server_py.relative_to(ctx.package_root).as_posix(),
                )
            )
    if "streamable_http_app" not in server_src:
        findings.append(
            finding(
                "route-matrix-gate",
                "PRIME-A05",
                "server must use streamable_http_app",
                file=server_py.relative_to(ctx.package_root).as_posix(),
            )
        )
    if specs_py.is_file() and catalog_py.is_file():
        specs_src = specs_py.read_text(encoding="utf-8")
        tool_count = specs_src.count("Tool(")
        if tool_count != 8:
            findings.append(
                finding(
                    "route-matrix-gate",
                    "PRIME-A05",
                    f"expected exactly 8 Tool() specs, found {tool_count}",
                    file=specs_py.relative_to(ctx.package_root).as_posix(),
                )
            )
        catalog_src = catalog_py.read_text(encoding="utf-8")
        enum_count = sum(
            1 for line in catalog_src.splitlines() if re.search(r'^\s+[A-Z_]+\s*=\s*"', line)
        )
        if enum_count != 8:
            findings.append(
                finding(
                    "route-matrix-gate",
                    "PRIME-A05",
                    f"ToolName enum must have 8 members, found {enum_count}",
                    file=catalog_py.relative_to(ctx.package_root).as_posix(),
                )
            )
    else:
        findings.append(
            finding("route-matrix-gate", "PRIME-A05", "missing tool_specs or tool_catalog")
        )
    return fail("route-matrix-gate", findings) if findings else ok("route-matrix-gate")


def e2e_only_anti_pattern(ctx: RunContext) -> StepResult:
    """Auth / deny / error must be covered in unit or contract, not only e2e."""
    findings = []
    unit_contract_roots = [
        ctx.package_root / "tests" / "unit",
        ctx.package_root / "tests" / "contract",
    ]
    required_tokens = {
        "PassportMissing": False,
        "passport_missing": False,
        "capability_denied": False,
        "is_error": False,
    }
    for root in unit_contract_roots:
        if not root.is_dir():
            continue
        for path in root.rglob("test_*.py"):
            text = path.read_text(encoding="utf-8")
            for token in required_tokens:
                if token in text:
                    required_tokens[token] = True
    # passport covered if either class or code string present
    passport_ok = required_tokens["PassportMissing"] or required_tokens["passport_missing"]
    if not passport_ok:
        findings.append(
            finding(
                "e2e-only-anti-pattern",
                "PRIME-A27",
                "pre-auth passport failure not covered outside e2e",
            )
        )
    if not required_tokens["capability_denied"]:
        findings.append(
            finding(
                "e2e-only-anti-pattern",
                "PRIME-A27",
                "capability deny not covered outside e2e",
            )
        )
    if not required_tokens["is_error"]:
        findings.append(
            finding(
                "e2e-only-anti-pattern",
                "PRIME-A27",
                "MCP is_error mapping not covered outside e2e",
            )
        )
    return fail("e2e-only-anti-pattern", findings) if findings else ok("e2e-only-anti-pattern")
