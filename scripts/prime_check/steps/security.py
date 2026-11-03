"""Security steps — package tree only."""

from __future__ import annotations

import json
import re
import subprocess

from scripts.prime_check.astlib import iter_py_files
from scripts.prime_check.context import RunContext
from scripts.prime_check.finding import StepResult
from scripts.prime_check.run_uv import run_uv
from scripts.prime_check.steps._util import fail, finding, ok

SECRET_PATTERNS = [
    re.compile(r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----"),
    re.compile(r"(?i)api[_-]?key\s*=\s*['\"][A-Za-z0-9_\-]{16,}"),
    re.compile(r"(?i)password\s*=\s*['\"][^'\"]{8,}['\"]"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
]

DEBUG_BYPASS = re.compile(
    r"(?i)(SKIP_AUTH|DEBUG_AUTH|if\s+True\s*:\s*#\s*bypass|TODO\s+remove\s+auth)"
)

PII_LOG = re.compile(r"(?i)(log|logger|print).{0,40}(email|ssn|password|passport|bearer\s)")


def no_secrets(ctx: RunContext) -> StepResult:
    findings = []
    roots = [
        ctx.package_root / "src",
        ctx.package_root / "tests",
        ctx.package_root / "scripts",
        ctx.package_root / "config",
    ]
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in {
                ".py",
                ".md",
                ".yml",
                ".yaml",
                ".json",
                ".toml",
                ".env.example",
            }:
                continue
            if path.name == "uv.lock":
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for pat in SECRET_PATTERNS:
                if pat.search(text):
                    # allow .env.example placeholders
                    if (
                        path.name == ".env.example"
                        and "password" in path.read_text(encoding="utf-8").lower()
                    ):
                        if "postgresql://user:password@" in text:
                            continue
                    findings.append(
                        finding(
                            "no-secrets",
                            "PRIME-A19",
                            f"secret-like pattern {pat.pattern[:40]}",
                            file=path.relative_to(ctx.package_root).as_posix(),
                        )
                    )
    return fail("no-secrets", findings) if findings else ok("no-secrets")


def bandit_step(ctx: RunContext) -> StepResult:
    res = run_uv(
        ["bandit", "-r", "src", "-q", "-f", "json"],
        cwd=ctx.package_root,
    )
    # bandit returns 1 when issues found
    try:
        payload = json.loads(res.stdout or "{}")
    except json.JSONDecodeError:
        if res.returncode != 0 and not res.stdout:
            return fail(
                "bandit",
                [finding("bandit", "PRIME-A16", "bandit failed", hint=res.stderr[:400])],
            )
        payload = {}
    results = payload.get("results") or []
    high = [r for r in results if r.get("issue_severity") in {"HIGH", "MEDIUM"}]
    if high:
        findings = [
            finding(
                "bandit",
                "PRIME-A16",
                f"{r.get('test_id')}: {r.get('issue_text')}",
                file=r.get("filename"),
                line=r.get("line_number"),
            )
            for r in high[:20]
        ]
        return fail("bandit", findings)
    return ok("bandit")


def dependency_audit(ctx: RunContext) -> StepResult:
    res = run_uv(["pip-audit", "--progress-spinner", "off"], cwd=ctx.package_root, timeout=900)
    if res.returncode != 0:
        return fail(
            "dependency-audit",
            [
                finding(
                    "dependency-audit",
                    "PRIME-A19",
                    "pip-audit reported vulnerabilities or failed",
                    hint=(res.stdout or res.stderr)[:800],
                )
            ],
        )
    return ok("dependency-audit")


def sbom(ctx: RunContext) -> StepResult:
    """CycloneDX SBOM from frozen lock export (P6 / release readiness)."""
    reports = ctx.package_root / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    out = reports / "sbom.cdx.json"
    argv = [
        "uv",
        "export",
        "--frozen",
        "--no-dev",
        "--no-hashes",
        "--no-annotate",
        "--format",
        "requirements-txt",
    ]
    try:
        proc = subprocess.run(
            argv,
            cwd=ctx.package_root,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return fail(
            "sbom",
            [finding("sbom", "PRIME-A19", "uv export failed to start", hint=str(exc))],
        )
    if proc.returncode != 0:
        return fail(
            "sbom",
            [
                finding(
                    "sbom",
                    "PRIME-A19",
                    "uv export --frozen failed",
                    hint=(proc.stderr or proc.stdout)[:800],
                )
            ],
        )
    components: list[dict[str, object]] = []
    for raw in (proc.stdout or "").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("-e "):
            continue
        # drop environment markers: name==ver ; marker
        pkg = line.split(";", 1)[0].strip()
        if "==" not in pkg:
            continue
        name, version = pkg.rsplit("==", 1)
        name = name.strip()
        version = version.strip()
        if not name or not version:
            continue
        purl = f"pkg:pypi/{name}@{version}"
        components.append(
            {
                "type": "library",
                "name": name,
                "version": version,
                "purl": purl,
                "bom-ref": purl,
            }
        )
    if not components:
        return fail(
            "sbom",
            [finding("sbom", "PRIME-A19", "uv export produced no package==version lines")],
        )
    root_name = "lime-ref-postgres-mcp"
    root_version = "2.0.2"
    root_purl = f"pkg:pypi/{root_name}@{root_version}"
    document = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "version": 1,
        "metadata": {
            "component": {
                "type": "application",
                "name": root_name,
                "version": root_version,
                "purl": root_purl,
                "bom-ref": root_purl,
            }
        },
        "components": components,
    }
    try:
        out.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    except OSError as exc:
        return fail(
            "sbom",
            [finding("sbom", "PRIME-A19", f"failed writing {out.name}", hint=str(exc))],
        )
    text = out.read_text(encoding="utf-8")
    if "CycloneDX" not in text or root_name not in text:
        return fail(
            "sbom",
            [finding("sbom", "PRIME-A19", "SBOM missing CycloneDX metadata or package name")],
        )
    if out.stat().st_size < 200:
        return fail(
            "sbom",
            [finding("sbom", "PRIME-A19", "SBOM file unexpectedly small")],
        )
    return ok("sbom", detail=f"reports/{out.name} ({len(components)} components)")


def no_debug_bypass(ctx: RunContext) -> StepResult:
    findings = []
    for path in iter_py_files(ctx.package_root, ctx.cfg.runtime_scope):
        text = path.read_text(encoding="utf-8")
        if DEBUG_BYPASS.search(text):
            findings.append(
                finding(
                    "no-debug-bypass",
                    "PRIME-A16",
                    "debug auth bypass pattern",
                    file=path.relative_to(ctx.package_root).as_posix(),
                )
            )
    return fail("no-debug-bypass", findings) if findings else ok("no-debug-bypass")


def pii_log_scan(ctx: RunContext) -> StepResult:
    findings = []
    for path in iter_py_files(ctx.package_root, ctx.cfg.runtime_scope):
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if PII_LOG.search(line):
                findings.append(
                    finding(
                        "pii-log-scan",
                        "PRIME-A16",
                        "possible PII in log/print",
                        file=path.relative_to(ctx.package_root).as_posix(),
                        line=i,
                    )
                )
    return fail("pii-log-scan", findings) if findings else ok("pii-log-scan")


def injection_fuzz(ctx: RunContext) -> StepResult:
    """SQL adversarial manifest + targeted pytest (P1b boundary)."""
    manifest = (
        ctx.package_root / "tests" / "unit" / "infrastructure" / "sql" / "adversarial_cases.py"
    )
    findings = []
    if not manifest.is_file():
        findings.append(
            finding(
                "injection-fuzz",
                "PRIME-A18",
                "missing adversarial_cases.py manifest",
                file="tests/unit/infrastructure/sql/adversarial_cases.py",
            )
        )
        return fail("injection-fuzz", findings)
    text = manifest.read_text(encoding="utf-8")
    for case_id in [f"Adv-{i}" for i in range(1, 11)]:
        if case_id not in text:
            findings.append(
                finding(
                    "injection-fuzz",
                    "PRIME-A18",
                    f"missing {case_id} in adversarial manifest",
                    file=manifest.relative_to(ctx.package_root).as_posix(),
                )
            )
    if findings:
        return fail("injection-fuzz", findings)
    res = run_uv(
        [
            "pytest",
            "-q",
            "--no-cov",
            "tests/unit/infrastructure/sql/test_adversarial_sql.py",
            "tests/unit/infrastructure/sql/test_analyze_then_guard.py",
        ],
        cwd=ctx.package_root,
        timeout=300,
    )
    if res.returncode != 0:
        return fail(
            "injection-fuzz",
            [
                finding(
                    "injection-fuzz",
                    "PRIME-A18",
                    "adversarial SQL pytest failed",
                    hint=(res.stdout or res.stderr)[-800:],
                )
            ],
        )
    return ok("injection-fuzz", detail="Adv-1..10 manifest + pipeline pytest green")


def zta_matrix_gate(ctx: RunContext) -> StepResult:
    """ZTA Z1-Z10 contract suite (P2 boundary)."""
    contract = ctx.package_root / "tests" / "contract" / "test_zta_matrix.py"
    findings = []
    if not contract.is_file():
        findings.append(
            finding(
                "zta-matrix-gate",
                "PRIME-A29",
                "missing tests/contract/test_zta_matrix.py",
                file="tests/contract/test_zta_matrix.py",
            )
        )
        return fail("zta-matrix-gate", findings)
    text = contract.read_text(encoding="utf-8")
    for i in range(1, 11):
        if f"test_z{i}" not in text:
            findings.append(
                finding(
                    "zta-matrix-gate",
                    "PRIME-A29",
                    f"missing Z{i} scenario in ZTA contract suite",
                    file=contract.relative_to(ctx.package_root).as_posix(),
                )
            )
    if findings:
        return fail("zta-matrix-gate", findings)
    res = run_uv(
        [
            "pytest",
            "-q",
            "--no-cov",
            "tests/contract/test_zta_matrix.py",
        ],
        cwd=ctx.package_root,
        timeout=300,
    )
    if res.returncode != 0:
        return fail(
            "zta-matrix-gate",
            [
                finding(
                    "zta-matrix-gate",
                    "PRIME-A29",
                    "ZTA matrix pytest failed",
                    hint=(res.stdout or res.stderr)[-800:],
                )
            ],
        )
    return ok("zta-matrix-gate", detail="Z1..Z10 contract suite green")
