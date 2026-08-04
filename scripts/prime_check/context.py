"""Shared run context for steps."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from scripts.prime_check.config import PrimeConfig


@dataclass(slots=True)
class RunContext:
    cfg: PrimeConfig
    package_root: Path
    only: set[str] | None = None
    diff_paths: set[str] | None = None
    cache: dict[str, Any] = field(default_factory=dict)

    def src_root(self) -> Path:
        return self.package_root / "src" / "lime_ref_postgres_mcp"
