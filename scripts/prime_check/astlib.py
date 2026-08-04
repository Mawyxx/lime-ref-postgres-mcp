"""stdlib ast helpers for architecture gates."""

from __future__ import annotations

import ast
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class PyModule:
    path: Path
    rel: str
    tree: ast.AST


def iter_py_files(root: Path, patterns: Iterable[str]) -> list[Path]:
    """Resolve simple `src/foo/**` globs under package root."""
    files: set[Path] = set()
    for pattern in patterns:
        clean = pattern.replace("/**", "").rstrip("/")
        base = root / clean
        if base.is_file() and base.suffix == ".py":
            files.add(base)
        elif base.is_dir():
            files.update(p for p in base.rglob("*.py") if p.is_file())
    return sorted(files)


def parse_module(path: Path, package_root: Path) -> PyModule:
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src, filename=str(path))
    rel = path.relative_to(package_root).as_posix()
    return PyModule(path=path, rel=rel, tree=tree)


def imported_modules(tree: ast.AST) -> set[str]:
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


def mccabe_complexity(func: ast.AST) -> int:
    """Simple McCabe: 1 + decision points."""
    score = 1
    for node in ast.walk(func):
        if isinstance(node, (ast.If, ast.For, ast.While, ast.And, ast.Or, ast.ExceptHandler)):
            score += 1
        elif isinstance(node, ast.comprehension):
            score += 1
    return score


def count_logic_lines(func: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """Rough logic LOC: non-docstring statements in body."""
    count = 0
    for stmt in func.body:
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
            if isinstance(stmt.value.value, str):
                continue
        count += 1
        count += sum(1 for _ in ast.walk(stmt) if isinstance(_, (ast.If, ast.For, ast.While)))
    return count


DENYLIST_CALLS = frozenset(
    {
        ("datetime", "now"),
        ("datetime", "utcnow"),
        ("time", "time"),
        ("time", "monotonic"),
        ("uuid", "uuid4"),
        ("random", "random"),
        ("random", "randint"),
        ("random", "choice"),
    }
)


def call_name(node: ast.Call) -> tuple[str, str] | None:
    func = node.func
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        return func.value.id, func.attr
    if isinstance(func, ast.Name):
        return "", func.id
    return None
