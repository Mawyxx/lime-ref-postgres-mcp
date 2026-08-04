"""Layer import-law tests (Prime A05 / TDD §4.2)."""

from __future__ import annotations

import ast
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[2] / "src" / "lime_ref_postgres_mcp"

BANNED_THIRD_PARTY = frozenset(
    {
        "mcp",
        "asyncpg",
        "httpx",
        "pglast",
        "uvicorn",
        "fastapi",
        "sqlalchemy",
        "pydantic",
        "pydantic_settings",
        "srcN",
        "lime_mcp_server",
        "jwt",
        "cryptography",
    }
)

DOMAIN_FORBIDDEN_INTERNAL = frozenset(
    {
        "lime_ref_postgres_mcp.bootstrap",
        "lime_ref_postgres_mcp.infrastructure",
        "lime_ref_postgres_mcp.presentation",
        "lime_ref_postgres_mcp.subscribers",
    }
)

APPLICATION_FORBIDDEN_INTERNAL = frozenset(
    {
        "lime_ref_postgres_mcp.bootstrap",
        "lime_ref_postgres_mcp.infrastructure",
        "lime_ref_postgres_mcp.presentation",
        "lime_ref_postgres_mcp.subscribers",
    }
)


def _iter_py_files(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*.py") if p.is_file())


def _module_name(path: Path) -> str:
    rel = path.relative_to(PACKAGE_ROOT.parent)
    parts = list(rel.with_suffix("").parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _imported_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
            names.add(node.module)
    return names


def _assert_no_banned(path: Path, names: set[str]) -> None:
    for banned in BANNED_THIRD_PARTY:
        for name in names:
            assert not (name == banned or name.startswith(banned + ".")), (
                f"{path}: banned import {name!r}"
            )


def test_domain_import_law() -> None:
    domain_root = PACKAGE_ROOT / "domain"
    for path in _iter_py_files(domain_root):
        names = _imported_names(path)
        _assert_no_banned(path, names)
        for forbidden in DOMAIN_FORBIDDEN_INTERNAL:
            for name in names:
                assert not name.startswith(forbidden), f"{path}: {name} violates domain law"
        assert "os" not in names, f"{path}: domain must not import os"


def test_application_import_law() -> None:
    app_root = PACKAGE_ROOT / "application"
    obs_prefix = "lime_ref_postgres_mcp.bootstrap.observability"
    for path in _iter_py_files(app_root):
        names = _imported_names(path)
        _assert_no_banned(path, names)
        for forbidden in APPLICATION_FORBIDDEN_INTERNAL:
            for name in names:
                if name.startswith(obs_prefix) or name == obs_prefix:
                    # TDD §9.6 — process-obs facade only
                    continue
                assert not name.startswith(forbidden), f"{path}: {name} violates application law"
        for name in names:
            if name.startswith("lime_ref_postgres_mcp.bootstrap") and not (
                name == obs_prefix or name.startswith(obs_prefix + ".")
            ):
                raise AssertionError(
                    f"{path}: application may only import {obs_prefix}, got {name}"
                )


def test_all_layer_packages_importable() -> None:
    import lime_ref_postgres_mcp
    import lime_ref_postgres_mcp.application.commands
    import lime_ref_postgres_mcp.application.context
    import lime_ref_postgres_mcp.application.ports
    import lime_ref_postgres_mcp.application.services
    import lime_ref_postgres_mcp.bootstrap
    import lime_ref_postgres_mcp.domain
    import lime_ref_postgres_mcp.domain.access
    import lime_ref_postgres_mcp.domain.agent
    import lime_ref_postgres_mcp.domain.auditing
    import lime_ref_postgres_mcp.domain.catalog
    import lime_ref_postgres_mcp.domain.common
    import lime_ref_postgres_mcp.domain.sql
    import lime_ref_postgres_mcp.infrastructure
    import lime_ref_postgres_mcp.infrastructure.clock
    import lime_ref_postgres_mcp.infrastructure.events
    import lime_ref_postgres_mcp.infrastructure.sql
    import lime_ref_postgres_mcp.presentation
    import lime_ref_postgres_mcp.presentation.mcp
    import lime_ref_postgres_mcp.subscribers

    assert lime_ref_postgres_mcp.__version__ == "0.1.0"
