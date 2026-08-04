"""Load and validate prime_check.config.yaml."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PACKAGE_ROOT / "scripts" / "prime_check.config.yaml"


@dataclass(slots=True)
class PrimeConfig:
    raw: dict[str, Any]
    package_root: Path = PACKAGE_ROOT

    @property
    def project_tier(self) -> str:
        return str(self.raw["project_tier"])

    @property
    def adoption_mode(self) -> str:
        return str(self.raw["adoption_mode"])

    @property
    def architecture(self) -> dict[str, Any]:
        return dict(self.raw.get("architecture") or {})

    @property
    def skipped_steps(self) -> dict[str, dict[str, str]]:
        return dict(self.raw.get("skipped_steps") or {})

    @property
    def ci(self) -> dict[str, str]:
        return dict(self.raw.get("ci") or {})

    @property
    def coverage(self) -> dict[str, Any]:
        return dict(self.raw.get("coverage") or {})

    @property
    def runtime_scope(self) -> list[str]:
        return list(self.raw.get("runtime_scope") or [])


def load_config(path: Path | None = None) -> PrimeConfig:
    cfg_path = path or CONFIG_PATH
    if not cfg_path.is_file():
        raise FileNotFoundError(f"missing config: {cfg_path}")
    data = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("config root must be a mapping")
    for key in ("project_tier", "adoption_mode", "stack", "runtime_scope", "architecture"):
        if key not in data:
            raise ValueError(f"config missing required key: {key}")
    if data.get("adoption_mode") != "greenfield":
        raise ValueError("adoption_mode must be greenfield for this package")
    if data.get("project_tier") != "PRIME":
        raise ValueError("project_tier must be PRIME")
    return PrimeConfig(raw=data)
