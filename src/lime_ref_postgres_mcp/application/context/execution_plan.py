"""ExecutionPlan — tagged union for DatabaseGateway dispatch."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ListSchemasPlan:
    pass


@dataclass(frozen=True, slots=True)
class ListTablesPlan:
    schema: str


@dataclass(frozen=True, slots=True)
class GetTableSchemaPlan:
    schema: str
    table: str


@dataclass(frozen=True, slots=True)
class SelectRowsPlan:
    schema: str
    table: str
    columns: tuple[str, ...] | None
    limit: int
    offset: int


@dataclass(frozen=True, slots=True)
class ExecuteReadonlyPlan:
    sql: str
    max_rows: int


@dataclass(frozen=True, slots=True)
class ExplainPlan:
    sql: str


@dataclass(frozen=True, slots=True)
class ExecuteWritePlan:
    sql: str
    target_table: str | None


@dataclass(frozen=True, slots=True)
class DatabaseStatsPlan:
    pass


type ExecutionPlan = (
    ListSchemasPlan
    | ListTablesPlan
    | GetTableSchemaPlan
    | SelectRowsPlan
    | ExecuteReadonlyPlan
    | ExplainPlan
    | ExecuteWritePlan
    | DatabaseStatsPlan
)


__all__ = [
    "DatabaseStatsPlan",
    "ExecuteReadonlyPlan",
    "ExecuteWritePlan",
    "ExecutionPlan",
    "ExplainPlan",
    "GetTableSchemaPlan",
    "ListSchemasPlan",
    "ListTablesPlan",
    "SelectRowsPlan",
]
