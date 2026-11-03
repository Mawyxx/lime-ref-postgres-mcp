from __future__ import annotations

import tomllib
from pathlib import Path

import lime_ref_postgres_mcp

_ROOT = Path(__file__).resolve().parents[2]


def test_package_version_matches_pyproject() -> None:
    data = tomllib.loads((_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert lime_ref_postgres_mcp.__version__ == data["project"]["version"]
