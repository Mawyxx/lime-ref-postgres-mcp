"""Clock / IdGenerator adapter tests."""

from __future__ import annotations

from datetime import UTC

from lime_ref_postgres_mcp.infrastructure.clock.system_clock import SystemClock
from lime_ref_postgres_mcp.infrastructure.clock.uuid_id_generator import Uuid4IdGenerator


def test_system_clock_utc() -> None:
    now = SystemClock().now_utc()
    assert now.tzinfo == UTC


def test_uuid_ids_unique() -> None:
    ids = Uuid4IdGenerator()
    a = ids.new_event_id()
    b = ids.new_request_id()
    assert len(a) == 36
    assert len(b) == 36
    assert a != b
