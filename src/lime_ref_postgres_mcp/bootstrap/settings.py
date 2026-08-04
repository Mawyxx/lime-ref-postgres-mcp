"""Process configuration from environment (bootstrap only — not domain)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from lime_ref_postgres_mcp.infrastructure.identity.domain_normalize import normalize_mcp_domain


class ConfigurationError(Exception):
    """Process-level config failure — not an agent DomainError."""

    def __init__(self, message: str, *, missing: tuple[str, ...] = ()) -> None:
        self.message = message
        self.missing = missing
        super().__init__(message)


_TRUE = frozenset({"1", "true", "yes", "on"})
_FALSE = frozenset({"0", "false", "no", "off", ""})
_LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR"})
_LOG_FORMATS = frozenset({"json", "console"})
_LOG_STREAMS = frozenset({"stderr", "stdout"})


def _require(env: dict[str, str], key: str) -> str:
    value = env.get(key, "").strip()
    if not value:
        raise ConfigurationError(f"Missing required environment variable: {key}", missing=(key,))
    return value


def _parse_bool(raw: str | None, *, default: bool) -> bool:
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in _TRUE:
        return True
    if normalized in _FALSE:
        return False
    raise ConfigurationError(f"Invalid boolean value: {raw!r}")


def _parse_positive_int(raw: str | None, *, default: int, key: str) -> int:
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw.strip())
    except ValueError as exc:
        raise ConfigurationError(f"Invalid integer for {key}: {raw!r}") from exc
    if value < 1:
        raise ConfigurationError(f"{key} must be >= 1, got {value}")
    return value


def _parse_port(raw: str | None, *, default: int, key: str) -> int:
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw.strip())
    except ValueError as exc:
        raise ConfigurationError(f"Invalid integer for {key}: {raw!r}") from exc
    if not 1 <= value <= 65535:
        raise ConfigurationError(f"{key} must be 1..65535, got {value}")
    return value


def _parse_bind_host(raw: str | None, *, default: str) -> str:
    if raw is None or not raw.strip():
        return default
    return raw.strip()


def _parse_choice(
    raw: str | None,
    *,
    default: str,
    allowed: frozenset[str],
    key: str,
    upper: bool = False,
) -> str:
    if raw is None or not raw.strip():
        return default
    value = raw.strip().upper() if upper else raw.strip().lower()
    if value not in allowed:
        raise ConfigurationError(f"Invalid {key}: {raw!r} (allowed: {sorted(allowed)})")
    return value


def _normalize_domain(raw: str) -> str:
    try:
        return normalize_mcp_domain(raw)
    except ValueError as exc:
        raise ConfigurationError(f"Invalid LIME_EXPECTED_DOMAIN: {exc}") from exc


@dataclass(frozen=True, slots=True)
class Settings:
    lime_expected_domain: str
    lime_jwks_url: str
    lime_expected_aud: str
    lime_jwks_cache_ttl_seconds: int
    lime_jwt_leeway_seconds: int
    agents_policy_path: Path
    policy_reload_ttl_seconds: int
    postgres_url: str
    pg_statement_timeout: str
    pg_lock_timeout: str
    pg_idle_in_transaction_timeout: str
    pg_max_result_bytes: int
    pg_pool_min_size: int
    pg_pool_max_size: int
    enable_console_event_sink: bool
    log_level: str
    log_format: str
    log_stream: str
    metrics_enabled: bool
    mcp_bind_host: str
    mcp_port: int

    @classmethod
    def from_env(cls, environ: dict[str, str] | None = None) -> Settings:
        env = dict(os.environ if environ is None else environ)
        policy_raw = env.get("AGENTS_POLICY_PATH", "./config/agents.json").strip()
        aud_raw = env.get("LIME_EXPECTED_AUD", "").strip()
        pool_min = _parse_positive_int(
            env.get("PG_POOL_MIN_SIZE"),
            default=1,
            key="PG_POOL_MIN_SIZE",
        )
        pool_max = _parse_positive_int(
            env.get("PG_POOL_MAX_SIZE"),
            default=4,
            key="PG_POOL_MAX_SIZE",
        )
        if pool_max < pool_min:
            raise ConfigurationError(
                f"PG_POOL_MAX_SIZE ({pool_max}) must be >= PG_POOL_MIN_SIZE ({pool_min})"
            )
        return cls(
            lime_expected_domain=_normalize_domain(_require(env, "LIME_EXPECTED_DOMAIN")),
            lime_jwks_url=_require(env, "LIME_JWKS_URL"),
            lime_expected_aud=aud_raw or "mcp",
            lime_jwks_cache_ttl_seconds=_parse_positive_int(
                env.get("LIME_JWKS_CACHE_TTL_SECONDS"),
                default=3600,
                key="LIME_JWKS_CACHE_TTL_SECONDS",
            ),
            lime_jwt_leeway_seconds=_parse_positive_int(
                env.get("LIME_JWT_VERIFY_LEEWAY_SECONDS"),
                default=120,
                key="LIME_JWT_VERIFY_LEEWAY_SECONDS",
            ),
            agents_policy_path=Path(policy_raw),
            policy_reload_ttl_seconds=_parse_positive_int(
                env.get("POLICY_RELOAD_TTL_SECONDS"),
                default=60,
                key="POLICY_RELOAD_TTL_SECONDS",
            ),
            postgres_url=_require(env, "POSTGRES_URL"),
            pg_statement_timeout=env.get("PG_STATEMENT_TIMEOUT", "5s").strip() or "5s",
            pg_lock_timeout=env.get("PG_LOCK_TIMEOUT", "2s").strip() or "2s",
            pg_idle_in_transaction_timeout=(
                env.get("PG_IDLE_IN_TRANSACTION_TIMEOUT", "10s").strip() or "10s"
            ),
            pg_max_result_bytes=_parse_positive_int(
                env.get("PG_MAX_RESULT_BYTES"),
                default=1_048_576,
                key="PG_MAX_RESULT_BYTES",
            ),
            pg_pool_min_size=pool_min,
            pg_pool_max_size=pool_max,
            enable_console_event_sink=_parse_bool(
                env.get("ENABLE_CONSOLE_EVENT_SINK"),
                default=True,
            ),
            log_level=_parse_choice(
                env.get("LIME_MCP_LOG_LEVEL"),
                default="INFO",
                allowed=_LOG_LEVELS,
                key="LIME_MCP_LOG_LEVEL",
                upper=True,
            ),
            log_format=_parse_choice(
                env.get("LIME_MCP_LOG_FORMAT"),
                default="json",
                allowed=_LOG_FORMATS,
                key="LIME_MCP_LOG_FORMAT",
            ),
            log_stream=_parse_choice(
                env.get("LIME_MCP_LOG_STREAM"),
                default="stderr",
                allowed=_LOG_STREAMS,
                key="LIME_MCP_LOG_STREAM",
            ),
            metrics_enabled=_parse_bool(env.get("LIME_MCP_METRICS"), default=True),
            mcp_bind_host=_parse_bind_host(
                env.get("LIME_MCP_BIND_HOST"),
                default="127.0.0.1",
            ),
            mcp_port=_parse_port(
                env.get("LIME_MCP_PORT"),
                default=8000,
                key="LIME_MCP_PORT",
            ),
        )


__all__ = ["ConfigurationError", "Settings"]
