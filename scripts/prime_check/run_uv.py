"""Subprocess helper: uv run … at package root."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class CmdResult:
    returncode: int
    stdout: str
    stderr: str
    argv: tuple[str, ...]


def run_uv(args: list[str], *, cwd: Path, timeout: int = 600) -> CmdResult:
    argv = ["uv", "run", *args]
    proc = subprocess.run(
        argv,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    return CmdResult(
        returncode=proc.returncode,
        stdout=proc.stdout or "",
        stderr=proc.stderr or "",
        argv=tuple(argv),
    )
