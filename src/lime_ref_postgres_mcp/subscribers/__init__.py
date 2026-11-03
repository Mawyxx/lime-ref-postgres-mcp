"""Optional event subscribers.

Shipped: ConsoleSink (event-system demo). Custom sinks via bus.subscribe.
"""

from __future__ import annotations

from lime_ref_postgres_mcp.subscribers.console_sink import ConsoleSink

__all__ = ["ConsoleSink"]
