"""JsonAgentPolicyStore — disk JSON policy with TTL/mtime cache."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from lime_ref_postgres_mcp.application.ports.clock import Clock
from lime_ref_postgres_mcp.bootstrap.observability import log
from lime_ref_postgres_mcp.domain.access.policy import PolicyDocument
from lime_ref_postgres_mcp.domain.common.errors import PolicyStoreFault
from lime_ref_postgres_mcp.domain.common.result import Err, Ok, Result


@dataclass(frozen=True, slots=True)
class _Snapshot:
    document: PolicyDocument
    mtime_ns: int
    checked_at: datetime


class JsonAgentPolicyStore:
    """AgentPolicyStore: immutable snapshot, lazy TTL then mtime, soft-keep on bad reload."""

    def __init__(
        self,
        path: Path,
        *,
        clock: Clock,
        reload_ttl_seconds: int,
    ) -> None:
        self._path = path
        self._clock = clock
        self._ttl = reload_ttl_seconds
        self._snap: _Snapshot | None = None
        self._lock = asyncio.Lock()

    async def current(self) -> Result[PolicyDocument, PolicyStoreFault]:
        async with self._lock:
            now = self._clock.now_utc()
            snap = self._snap
            if snap is not None and (now - snap.checked_at).total_seconds() < self._ttl:
                return Ok(snap.document)
            return self._reload(now)

    def _reload(self, now: datetime) -> Result[PolicyDocument, PolicyStoreFault]:
        mtime_result = self._stat_mtime_ns()
        if isinstance(mtime_result, Err):
            return self._fail_or_keep(mtime_result.error, now)

        mtime_ns = mtime_result.value
        snap = self._snap
        if snap is not None and mtime_ns == snap.mtime_ns:
            self._snap = _Snapshot(
                document=snap.document,
                mtime_ns=snap.mtime_ns,
                checked_at=now,
            )
            return Ok(snap.document)

        first_load = snap is None
        loaded = self._load_from_disk()
        if isinstance(loaded, Err):
            return self._fail_or_keep(loaded.error, now)

        self._snap = _Snapshot(
            document=loaded.value,
            mtime_ns=mtime_ns,
            checked_at=now,
        )
        log(
            "policy",
            "policy.load" if first_load else "policy.reload",
            path=str(self._path),
            agents=len(loaded.value.agents),
        )
        return Ok(loaded.value)

    def _fail_or_keep(
        self, fault: PolicyStoreFault, now: datetime
    ) -> Result[PolicyDocument, PolicyStoreFault]:
        snap = self._snap
        if snap is None:
            return Err(fault)
        self._snap = _Snapshot(
            document=snap.document,
            mtime_ns=snap.mtime_ns,
            checked_at=now,
        )
        log(
            "policy",
            "policy.soft_keep",
            level="WARNING",
            path=str(self._path),
            code=str(fault.context.get("reason_code") or fault.invariant_id),
            invariant_id=fault.invariant_id,
        )
        return Ok(snap.document)

    def _stat_mtime_ns(self) -> Result[int, PolicyStoreFault]:
        try:
            return Ok(self._path.stat().st_mtime_ns)
        except FileNotFoundError:
            return Err(
                PolicyStoreFault(
                    invariant_id="policy.store_unavailable",
                    message="policy file not found",
                    context={"reason_code": "file_not_found", "path": str(self._path)},
                )
            )
        except OSError as exc:
            return Err(
                PolicyStoreFault(
                    invariant_id="policy.store_unavailable",
                    message="policy file unreadable",
                    context={
                        "reason_code": "io_error",
                        "path": str(self._path),
                        "errno": getattr(exc, "errno", None),
                    },
                )
            )

    def _load_from_disk(self) -> Result[PolicyDocument, PolicyStoreFault]:
        try:
            raw = self._read_bytes()
        except FileNotFoundError:
            return Err(
                PolicyStoreFault(
                    invariant_id="policy.store_unavailable",
                    message="policy file not found",
                    context={"reason_code": "file_not_found", "path": str(self._path)},
                )
            )
        except OSError as exc:
            return Err(
                PolicyStoreFault(
                    invariant_id="policy.store_unavailable",
                    message="policy file unreadable",
                    context={
                        "reason_code": "io_error",
                        "path": str(self._path),
                        "errno": getattr(exc, "errno", None),
                    },
                )
            )
        try:
            data: Any = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return Err(
                PolicyStoreFault(
                    invariant_id="policy.store_invalid",
                    message="policy file is not valid JSON",
                    context={"reason_code": "parse_error", "path": str(self._path)},
                )
            )
        if not isinstance(data, dict):
            return Err(
                PolicyStoreFault(
                    invariant_id="policy.store_invalid",
                    message="policy root must be an object",
                    context={"reason_code": "schema_invalid", "path": str(self._path)},
                )
            )
        mapped = PolicyDocument.from_mapping(data)
        if isinstance(mapped, Err):
            return Err(
                PolicyStoreFault(
                    invariant_id="policy.store_invalid",
                    message=mapped.error.message,
                    context={
                        "reason_code": "schema_invalid",
                        "path": str(self._path),
                        "cause_invariant_id": mapped.error.invariant_id,
                        **dict(mapped.error.context),
                    },
                )
            )
        return Ok(mapped.value)

    def _read_bytes(self) -> bytes:
        """Hook for tests to count disk reads."""
        return self._path.read_bytes()


__all__ = ["JsonAgentPolicyStore"]
