"""Ops / prod-config gates."""

from __future__ import annotations

from scripts.prime_check.context import RunContext
from scripts.prime_check.finding import StepResult
from scripts.prime_check.steps._util import fail, finding, ok

REQUIRED_ENV = (
    "LIME_EXPECTED_DOMAIN",
    "LIME_JWKS_URL",
    "POSTGRES_URL",
)


def prod_config(ctx: RunContext) -> StepResult:
    example = ctx.package_root / ".env.example"
    settings = ctx.package_root / "src" / "lime_ref_postgres_mcp" / "bootstrap" / "settings.py"
    findings = []
    if not example.is_file():
        findings.append(
            finding("prod-config", "PRIME-A23", ".env.example missing"),
        )
    else:
        text = example.read_text(encoding="utf-8")
        for key in REQUIRED_ENV:
            if key not in text:
                findings.append(
                    finding(
                        "prod-config",
                        "PRIME-A23",
                        f".env.example missing {key}",
                        file=".env.example",
                    )
                )
    if settings.is_file():
        src = settings.read_text(encoding="utf-8")
        for key in REQUIRED_ENV:
            if key not in src:
                findings.append(
                    finding(
                        "prod-config",
                        "PRIME-A23",
                        f"Settings.from_env missing {key}",
                        file=settings.relative_to(ctx.package_root).as_posix(),
                    )
                )
    else:
        findings.append(finding("prod-config", "PRIME-A23", "settings.py missing"))
    return fail("prod-config", findings) if findings else ok("prod-config")
