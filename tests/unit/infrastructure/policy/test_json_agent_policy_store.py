"""JsonAgentPolicyStore unit tests (P-1..P-8)."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import pytest
from tests.fakes.fixed_clock import FixedClock

from lime_ref_postgres_mcp.domain.common.errors import PolicyStoreFault
from lime_ref_postgres_mcp.domain.common.result import Err, Ok
from lime_ref_postgres_mcp.infrastructure.policy.json_agent_policy_store import (
    JsonAgentPolicyStore,
)

VALID_POLICY = {
    "max_rows": 100,
    "agents": {
        "agent_ok": {"permissions": ["READ_SCHEMA", "READ_DATA"]},
        "agent_writer": {"permissions": ["READ_SCHEMA", "READ_DATA", "WRITE_DATA"]},
    },
}


class CountingStore(JsonAgentPolicyStore):
    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]
        self.read_count = 0

    def _read_bytes(self) -> bytes:
        self.read_count += 1
        return super()._read_bytes()


def _write(path: Path, data: object) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")
    # Ensure mtime_ns advances on fast Windows rewrites (same-second FS resolution).
    st = path.stat()
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000))


@pytest.mark.asyncio
async def test_p1_valid_load(tmp_path: Path) -> None:
    path = tmp_path / "agents.json"
    _write(path, VALID_POLICY)
    store = CountingStore(path, clock=FixedClock(), reload_ttl_seconds=60)
    result = await store.current()
    assert isinstance(result, Ok)
    assert "agent_ok" in result.value.agents
    assert store.read_count == 1


@pytest.mark.asyncio
async def test_p2_missing_file(tmp_path: Path) -> None:
    store = JsonAgentPolicyStore(
        tmp_path / "missing.json",
        clock=FixedClock(),
        reload_ttl_seconds=60,
    )
    result = await store.current()
    assert isinstance(result, Err)
    assert isinstance(result.error, PolicyStoreFault)
    assert result.error.context.get("reason_code") == "file_not_found"


@pytest.mark.asyncio
async def test_p3_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "agents.json"
    path.write_text("{not-json", encoding="utf-8")
    store = JsonAgentPolicyStore(path, clock=FixedClock(), reload_ttl_seconds=60)
    result = await store.current()
    assert isinstance(result, Err)
    assert result.error.context.get("reason_code") == "parse_error"


@pytest.mark.asyncio
async def test_p4_schema_invalid(tmp_path: Path) -> None:
    path = tmp_path / "agents.json"
    _write(path, {"max_rows": 0, "agents": {}})
    store = JsonAgentPolicyStore(path, clock=FixedClock(), reload_ttl_seconds=60)
    result = await store.current()
    assert isinstance(result, Err)
    assert result.error.context.get("reason_code") == "schema_invalid"


@pytest.mark.asyncio
async def test_p5_within_ttl_ignores_mtime(tmp_path: Path) -> None:
    path = tmp_path / "agents.json"
    _write(path, VALID_POLICY)
    clock = FixedClock()
    store = CountingStore(path, clock=clock, reload_ttl_seconds=60)
    first = await store.current()
    assert isinstance(first, Ok)
    _write(
        path,
        {
            "max_rows": 50,
            "agents": {"only_new": {"permissions": ["READ_SCHEMA"]}},
        },
    )
    second = await store.current()
    assert isinstance(second, Ok)
    assert second.value is first.value
    assert "agent_ok" in second.value.agents
    assert store.read_count == 1


@pytest.mark.asyncio
async def test_p6_past_ttl_same_mtime_no_reread(tmp_path: Path) -> None:
    path = tmp_path / "agents.json"
    _write(path, VALID_POLICY)
    clock = FixedClock()
    store = CountingStore(path, clock=clock, reload_ttl_seconds=60)
    first = await store.current()
    assert isinstance(first, Ok)
    clock.advance(60)
    second = await store.current()
    assert isinstance(second, Ok)
    assert second.value is first.value
    assert store.read_count == 1


@pytest.mark.asyncio
async def test_p7_past_ttl_new_file_replaces(tmp_path: Path) -> None:
    path = tmp_path / "agents.json"
    _write(path, VALID_POLICY)
    clock = FixedClock()
    store = CountingStore(path, clock=clock, reload_ttl_seconds=60)
    first = await store.current()
    assert isinstance(first, Ok)
    clock.advance(60)
    _write(
        path,
        {
            "max_rows": 10,
            "agents": {"agent_new": {"permissions": ["READ_SCHEMA"]}},
        },
    )
    second = await store.current()
    assert isinstance(second, Ok)
    assert "agent_new" in second.value.agents
    assert "agent_ok" not in second.value.agents
    assert store.read_count == 2


@pytest.mark.asyncio
async def test_p8_soft_keep_on_corrupt_reload(tmp_path: Path) -> None:
    path = tmp_path / "agents.json"
    _write(path, VALID_POLICY)
    clock = FixedClock()
    store = CountingStore(path, clock=clock, reload_ttl_seconds=60)
    first = await store.current()
    assert isinstance(first, Ok)
    clock.advance(60)
    path.write_text("{broken", encoding="utf-8")
    second = await store.current()
    assert isinstance(second, Ok)
    assert second.value is first.value
    assert "agent_ok" in second.value.agents
    clock.advance(30)
    third = await store.current()
    assert isinstance(third, Ok)
    assert third.value is first.value
    assert store.read_count == 2


@pytest.mark.asyncio
async def test_concurrent_current_under_lock(tmp_path: Path) -> None:
    path = tmp_path / "agents.json"
    _write(path, VALID_POLICY)
    store = CountingStore(path, clock=FixedClock(), reload_ttl_seconds=60)
    results = await asyncio.gather(*[store.current() for _ in range(20)])
    assert all(isinstance(r, Ok) for r in results)
    docs = [r.value for r in results if isinstance(r, Ok)]
    assert all(d is docs[0] for d in docs)
    assert store.read_count == 1


@pytest.mark.asyncio
async def test_non_object_json_root(tmp_path: Path) -> None:
    path = tmp_path / "agents.json"
    path.write_text("[1,2,3]", encoding="utf-8")
    store = JsonAgentPolicyStore(path, clock=FixedClock(), reload_ttl_seconds=60)
    result = await store.current()
    assert isinstance(result, Err)
    assert result.error.context.get("reason_code") == "schema_invalid"


@pytest.mark.asyncio
async def test_soft_keep_on_missing_after_good(tmp_path: Path) -> None:
    path = tmp_path / "agents.json"
    _write(path, VALID_POLICY)
    clock = FixedClock()
    store = JsonAgentPolicyStore(path, clock=clock, reload_ttl_seconds=60)
    first = await store.current()
    assert isinstance(first, Ok)
    clock.advance(60)
    path.unlink()
    second = await store.current()
    assert isinstance(second, Ok)
    assert second.value is first.value


@pytest.mark.asyncio
async def test_stat_oserror_first_load(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "agents.json"
    _write(path, VALID_POLICY)

    def boom() -> None:
        raise OSError(13, "permission denied")

    monkeypatch.setattr(Path, "stat", lambda self: boom())  # type: ignore[misc]
    store = JsonAgentPolicyStore(path, clock=FixedClock(), reload_ttl_seconds=60)
    result = await store.current()
    assert isinstance(result, Err)
    assert result.error.context.get("reason_code") == "io_error"


@pytest.mark.asyncio
async def test_read_oserror_first_load(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "agents.json"
    _write(path, VALID_POLICY)

    def boom_read(_self: JsonAgentPolicyStore) -> bytes:
        raise OSError(13, "permission denied")

    store = JsonAgentPolicyStore(path, clock=FixedClock(), reload_ttl_seconds=60)
    monkeypatch.setattr(JsonAgentPolicyStore, "_read_bytes", boom_read)
    result = await store.current()
    assert isinstance(result, Err)
    assert result.error.context.get("reason_code") == "io_error"


@pytest.mark.asyncio
async def test_read_file_not_found_after_stat(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "agents.json"
    _write(path, VALID_POLICY)

    def boom_read(_self: JsonAgentPolicyStore) -> bytes:
        raise FileNotFoundError(path)

    store = JsonAgentPolicyStore(path, clock=FixedClock(), reload_ttl_seconds=60)
    monkeypatch.setattr(JsonAgentPolicyStore, "_read_bytes", boom_read)
    result = await store.current()
    assert isinstance(result, Err)
    assert result.error.context.get("reason_code") == "file_not_found"


@pytest.mark.asyncio
async def test_double_check_inside_lock(tmp_path: Path) -> None:
    """Within TTL, concurrent callers share one snapshot under the lock."""
    path = tmp_path / "agents.json"
    _write(path, VALID_POLICY)
    store = CountingStore(path, clock=FixedClock(), reload_ttl_seconds=60)
    assert isinstance(await store.current(), Ok)
    results = await asyncio.gather(store.current(), store.current())
    assert all(isinstance(r, Ok) for r in results)
    assert store.read_count == 1
