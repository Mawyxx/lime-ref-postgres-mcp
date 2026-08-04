"""ToolCapability enum — product SSOT for agent permissions."""

from __future__ import annotations

from enum import StrEnum


class ToolCapability(StrEnum):
    """Permission levers (not coarse read|write mode)."""

    READ_SCHEMA = "READ_SCHEMA"
    READ_DATA = "READ_DATA"
    WRITE_DATA = "WRITE_DATA"
    DDL = "DDL"
    ADMIN = "ADMIN"


__all__ = ["ToolCapability"]
