"""Explicit Ok/Err algebra for application and domain outcomes (Prime A10)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Ok[T]:
    value: T


@dataclass(frozen=True, slots=True)
class Err[E]:
    error: E


type Result[T, E] = Ok[T] | Err[E]


def is_ok[T, E](result: Result[T, E]) -> bool:
    return isinstance(result, Ok)


def is_err[T, E](result: Result[T, E]) -> bool:
    return isinstance(result, Err)


def unwrap[T, E](result: Result[T, E]) -> T:
    if isinstance(result, Ok):
        return result.value
    raise ValueError(f"unwrap called on Err: {result.error!r}")


def unwrap_err[T, E](result: Result[T, E]) -> E:
    if isinstance(result, Err):
        return result.error
    raise ValueError(f"unwrap_err called on Ok: {result.value!r}")


__all__ = ["Err", "Ok", "Result", "is_err", "is_ok", "unwrap", "unwrap_err"]
