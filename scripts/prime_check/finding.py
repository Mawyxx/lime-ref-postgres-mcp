"""Finding and StepResult models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Status(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    SKIPPED = "SKIPPED"
    ERROR = "ERROR"


@dataclass(frozen=True, slots=True)
class Finding:
    rule_id: str
    step: str
    priority: str
    issue: str
    file: str | None = None
    line: int | None = None
    symbol: str | None = None
    snippet: str | None = None
    hint: str | None = None
    rerun: str | None = None


@dataclass(slots=True)
class StepResult:
    step_id: str
    status: Status
    duration_ms: int
    findings: list[Finding] = field(default_factory=list)
    skip_adr: str | None = None
    detail: str | None = None
    extras: dict[str, Any] = field(default_factory=dict)
