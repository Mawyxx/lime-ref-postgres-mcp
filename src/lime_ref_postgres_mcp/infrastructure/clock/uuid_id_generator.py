"""Production IdGenerator adapter — UUID4 strings."""

from __future__ import annotations

from uuid import uuid4


class Uuid4IdGenerator:
    def new_event_id(self) -> str:
        return str(uuid4())

    def new_request_id(self) -> str:
        return str(uuid4())
