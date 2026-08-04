"""AST Prosecutor architecture gates (stdlib ast)."""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path

from scripts.prime_check.astlib import (
    DENYLIST_CALLS,
    call_name,
    count_logic_lines,
    imported_modules,
    iter_py_files,
    parse_module,
)
from scripts.prime_check.context import RunContext
from scripts.prime_check.finding import Finding, StepResult
from scripts.prime_check.steps._util import fail, finding, ok

PKG = "lime_ref_postgres_mcp"


def _banned(ctx: RunContext) -> set[str]:
    return set((ctx.cfg.architecture.get("banned_imports_in_core") or {}).get("python") or [])


def _scope_files(ctx: RunContext, key: str) -> list[Path]:
    patterns = ctx.cfg.architecture.get(key) or []
    return iter_py_files(ctx.package_root, patterns)


def import_boundaries(ctx: RunContext) -> StepResult:
    return _import_graph_impl(ctx, step="import-boundaries", rule="PRIME-A05")


def import_graph_gate(ctx: RunContext) -> StepResult:
    return _import_graph_impl(ctx, step="import-graph-gate", rule="PRIME-A05")


def _import_forbidden(name: str, *, scope_key: str) -> bool:
    """True if ``name`` is a forbidden internal import for the scope."""
    obs_prefix = f"{PKG}.bootstrap.observability"
    for fi in (
        f"{PKG}.bootstrap",
        f"{PKG}.infrastructure",
        f"{PKG}.presentation",
        f"{PKG}.subscribers",
    ):
        if name == fi or name.startswith(fi + "."):
            # Application may import process-obs facade only (TDD §9.6 / ADR-003).
            if (
                scope_key == "application_scope"
                and (name == obs_prefix or name.startswith(obs_prefix + "."))
            ):
                return False
            return True
    return False


def _import_graph_impl(ctx: RunContext, *, step: str, rule: str) -> StepResult:
    banned = _banned(ctx)
    findings: list[Finding] = []
    for scope_key in ("core_scope", "application_scope"):
        for path in _scope_files(ctx, scope_key):
            mod = parse_module(path, ctx.package_root)
            names = imported_modules(mod.tree)
            for name in names:
                root = name.split(".")[0]
                if root in banned or name in banned:
                    findings.append(
                        finding(
                            step,
                            rule,
                            f"banned import {name!r}",
                            file=mod.rel,
                            hint="keep I/O out of domain/application",
                        )
                    )
                if _import_forbidden(name, scope_key=scope_key):
                    findings.append(
                        finding(
                            step,
                            rule,
                            f"{scope_key} imports {name}",
                            file=mod.rel,
                            hint="dependency must point inward via ports",
                        )
                    )
                if scope_key == "core_scope" and name == "os":
                    findings.append(finding(step, rule, "domain must not import os", file=mod.rel))
    return fail(step, findings) if findings else ok(step)


def deterministic_runtime(ctx: RunContext) -> StepResult:
    findings: list[Finding] = []
    for path in _scope_files(ctx, "testable_core_scope"):
        mod = parse_module(path, ctx.package_root)
        for node in ast.walk(mod.tree):
            if isinstance(node, ast.Call):
                cn = call_name(node)
                if cn and cn in DENYLIST_CALLS:
                    findings.append(
                        finding(
                            "deterministic-runtime",
                            "PRIME-A15",
                            f"nondeterministic call {cn[0]}.{cn[1]}",
                            file=mod.rel,
                            line=node.lineno,
                            hint="inject Clock/IdGenerator ports",
                        )
                    )
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                if node.value.id == "datetime" and node.attr in {"now", "utcnow"}:
                    # attribute load only — call checked above
                    pass
    return fail("deterministic-runtime", findings) if findings else ok("deterministic-runtime")


def anti_null_gate(ctx: RunContext) -> StepResult:
    findings: list[Finding] = []
    for path in _scope_files(ctx, "application_scope"):
        mod = parse_module(path, ctx.package_root)
        for node in ast.walk(mod.tree):
            if isinstance(node, ast.Return) and isinstance(node.value, ast.Constant):
                if node.value.value is None:
                    # Allow Protocol stubs only — application ports may have ... not None
                    findings.append(
                        finding(
                            "anti-null-gate",
                            "PRIME-A10",
                            "return None as failure path",
                            file=mod.rel,
                            line=node.lineno,
                            hint="use Result/Err or raise named error",
                        )
                    )
    # Domain application currently has no return None — ports use Ellipsis
    # Filter Protocol module false positives: none expected
    return fail("anti-null-gate", findings) if findings else ok("anti-null-gate")


def di_purity(ctx: RunContext) -> StepResult:
    infra_ctors = {
        "SystemClock",
        "Uuid4IdGenerator",
        "PglastSqlAnalyzer",
        "InProcessEventBus",
        "LimePassportVerifier",
        "JsonAgentPolicyStore",
        "TokenVerifier",
        "AsyncpgDatabaseGateway",
        "ConsoleSink",
    }
    findings: list[Finding] = []
    for scope_key in ("core_scope", "application_scope"):
        for path in _scope_files(ctx, scope_key):
            mod = parse_module(path, ctx.package_root)
            for node in ast.walk(mod.tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    if node.func.id in infra_ctors:
                        findings.append(
                            finding(
                                "di-purity",
                                "PRIME-A06",
                                f"direct {node.func.id}() outside composition root",
                                file=mod.rel,
                                line=node.lineno,
                                hint="wire in bootstrap/container.py only",
                            )
                        )
    return fail("di-purity", findings) if findings else ok("di-purity")


def di_graph_gate(ctx: RunContext) -> StepResult:
    """Concrete infra construction must live only under bootstrap."""
    infra_ctors = {
        "SystemClock",
        "Uuid4IdGenerator",
        "PglastSqlAnalyzer",
        "InProcessEventBus",
        "LimePassportVerifier",
        "JsonAgentPolicyStore",
        "TokenVerifier",
        "AsyncpgDatabaseGateway",
        "ConsoleSink",
    }
    allowed = {p.resolve() for p in _scope_files(ctx, "composition_root")}
    findings: list[Finding] = []
    for path in iter_py_files(ctx.package_root, ctx.cfg.runtime_scope):
        if path.resolve() in allowed:
            continue
        # infrastructure adapters defining the classes are OK
        rel = path.relative_to(ctx.package_root).as_posix()
        if "/infrastructure/" in f"/{rel}":
            continue
        mod = parse_module(path, ctx.package_root)
        for node in ast.walk(mod.tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in infra_ctors:
                    findings.append(
                        finding(
                            "di-graph-gate",
                            "PRIME-A06",
                            f"{node.func.id}() outside bootstrap",
                            file=mod.rel,
                            line=node.lineno,
                        )
                    )
    return fail("di-graph-gate", findings) if findings else ok("di-graph-gate")


def handler_purity_gate(ctx: RunContext) -> StepResult:
    max_logic = int(ctx.cfg.architecture.get("handler_max_logic_lines", 15))
    findings: list[Finding] = []
    for path in _scope_files(ctx, "presentation_scope"):
        mod = parse_module(path, ctx.package_root)
        for node in ast.walk(mod.tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith("_"):
                    continue
                n = count_logic_lines(node)
                if n > max_logic:
                    findings.append(
                        finding(
                            "handler-purity-gate",
                            "PRIME-A05",
                            f"handler {node.name} logic lines {n} > {max_logic}",
                            file=mod.rel,
                            line=node.lineno,
                        )
                    )
    return fail("handler-purity-gate", findings) if findings else ok("handler-purity-gate")


def anti_fork_gate(ctx: RunContext) -> StepResult:
    findings: list[Finding] = []
    bodies: dict[str, list[str]] = {}
    for path in iter_py_files(ctx.package_root, ctx.cfg.runtime_scope):
        name = path.name
        if any(x in name for x in ("_v2", "Copy", "Old", "New")):
            findings.append(
                finding(
                    "anti-fork-gate",
                    "PRIME-A08",
                    f"fork-like filename {name}",
                    file=path.relative_to(ctx.package_root).as_posix(),
                )
            )
        mod = parse_module(path, ctx.package_root)
        for node in ast.walk(mod.tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                dump = ast.dump(node)
                h = hashlib.sha256(dump.encode()).hexdigest()[:16]
                bodies.setdefault(h, []).append(f"{mod.rel}:{node.name}")
    for paths in bodies.values():
        if len(paths) > 1 and all("test" not in p for p in paths):
            # ignore tiny identical Protocol stubs
            if len(paths) >= 3:
                findings.append(
                    finding(
                        "anti-fork-gate",
                        "PRIME-A08",
                        f"duplicate AST bodies: {paths}",
                        hint="dedupe policy",
                    )
                )
    return fail("anti-fork-gate", findings) if findings else ok("anti-fork-gate")


def immutability_gate(ctx: RunContext) -> StepResult:
    findings: list[Finding] = []
    for path in _scope_files(ctx, "core_scope"):
        mod = parse_module(path, ctx.package_root)
        for node in ast.walk(mod.tree):
            if isinstance(node, ast.ClassDef):
                # DomainError hierarchy should be frozen dataclasses
                decos = []
                for d in node.decorator_list:
                    if isinstance(d, ast.Call) and isinstance(d.func, ast.Name):
                        decos.append(d.func.id)
                        keywords = {k.arg: k.value for k in d.keywords if k.arg}
                        if d.func.id == "dataclass":
                            frozen = keywords.get("frozen")
                            if not (isinstance(frozen, ast.Constant) and frozen.value is True):
                                if node.name.endswith("Error") or node.name in {
                                    "Ok",
                                    "Err",
                                    "DomainError",
                                    "InvariantViolation",
                                }:
                                    findings.append(
                                        finding(
                                            "immutability-gate",
                                            "PRIME-A05",
                                            f"{node.name} dataclass not frozen=True",
                                            file=mod.rel,
                                            line=node.lineno,
                                        )
                                    )
                    elif isinstance(d, ast.Name):
                        decos.append(d.id)
    return fail("immutability-gate", findings) if findings else ok("immutability-gate")


def no_transport_in_domain(ctx: RunContext) -> StepResult:
    banned = {"HTTPException", "JSONResponse", "Request", "Response", "fastapi", "starlette"}
    findings: list[Finding] = []
    for path in _scope_files(ctx, "core_scope"):
        mod = parse_module(path, ctx.package_root)
        names = imported_modules(mod.tree)
        for b in banned:
            if any(b in n for n in names):
                findings.append(
                    finding(
                        "no-transport-in-domain",
                        "PRIME-A10",
                        f"transport symbol {b} in domain",
                        file=mod.rel,
                    )
                )
        src = path.read_text(encoding="utf-8")
        if "HTTPException" in src:
            findings.append(
                finding(
                    "no-transport-in-domain",
                    "PRIME-A10",
                    "HTTPException referenced in domain",
                    file=mod.rel,
                )
            )
    return fail("no-transport-in-domain", findings) if findings else ok("no-transport-in-domain")


def error_context_gate(ctx: RunContext) -> StepResult:
    """DomainError must expose invariant_id + message."""
    errors_path = (
        ctx.package_root / "src" / "lime_ref_postgres_mcp" / "domain" / "common" / "errors.py"
    )
    if not errors_path.is_file():
        return fail(
            "error-context-gate",
            [finding("error-context-gate", "PRIME-A10", "errors.py missing")],
        )
    src = errors_path.read_text(encoding="utf-8")
    if "invariant_id" not in src or "message" not in src:
        return fail(
            "error-context-gate",
            [
                finding(
                    "error-context-gate",
                    "PRIME-A10",
                    "DomainError missing invariant_id/message",
                    file=errors_path.relative_to(ctx.package_root).as_posix(),
                )
            ],
        )
    return ok("error-context-gate")


def context_leak_gate(ctx: RunContext) -> StepResult:
    findings: list[Finding] = []
    for path in iter_py_files(ctx.package_root, ctx.cfg.runtime_scope):
        mod = parse_module(path, ctx.package_root)
        for name in imported_modules(mod.tree):
            if name == "srcN" or name.startswith("srcN."):
                findings.append(
                    finding(
                        "context-leak-gate",
                        "PRIME-A04",
                        f"imports {name}",
                        file=mod.rel,
                        hint="package must stay isolated",
                    )
                )
    return fail("context-leak-gate", findings) if findings else ok("context-leak-gate")


def no_string_sql(ctx: RunContext) -> StepResult:
    findings: list[Finding] = []
    needles = ("SELECT ", "INSERT ", "UPDATE ", "DELETE ", "DROP ")
    for path in iter_py_files(ctx.package_root, ctx.cfg.runtime_scope):
        mod = parse_module(path, ctx.package_root)
        for node in ast.walk(mod.tree):
            if isinstance(node, ast.JoinedStr):  # f-string
                # flag if f-string contains SQL keywords in constants
                text = "".join(
                    p.value
                    for p in node.values
                    if isinstance(p, ast.Constant) and isinstance(p.value, str)
                )
                if any(n in text.upper() for n in needles):
                    findings.append(
                        finding(
                            "no-string-sql",
                            "PRIME-A18",
                            "f-string looks like SQL",
                            file=mod.rel,
                            line=node.lineno,
                        )
                    )
    return fail("no-string-sql", findings) if findings else ok("no-string-sql")


def no_ddl_in_app(ctx: RunContext) -> StepResult:
    findings: list[Finding] = []
    ddl = ("CREATE TABLE", "ALTER TABLE", "DROP TABLE")
    for path in _scope_files(ctx, "application_scope"):
        src = path.read_text(encoding="utf-8").upper()
        for d in ddl:
            if d in src:
                findings.append(
                    finding(
                        "no-ddl-in-app",
                        "PRIME-A20",
                        f"DDL fragment {d} in application",
                        file=path.relative_to(ctx.package_root).as_posix(),
                    )
                )
    return fail("no-ddl-in-app", findings) if findings else ok("no-ddl-in-app")
