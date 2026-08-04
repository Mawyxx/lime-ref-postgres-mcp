"""Safe identifier quoting for select_rows (allowlist, not value bind)."""

from __future__ import annotations

import re

from lime_ref_postgres_mcp.domain.common.errors import DatabaseFault
from lime_ref_postgres_mcp.domain.common.result import Err, Ok, Result

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,62}$")


def quote_ident(name: str) -> Result[str, DatabaseFault]:
    if not _IDENT_RE.fullmatch(name):
        return Err(
            DatabaseFault(
                invariant_id="database.execution_failed",
                message="Database operation failed",
                context={},
            )
        )
    return Ok('"' + name.replace('"', '""') + '"')


__all__ = ["quote_ident"]
