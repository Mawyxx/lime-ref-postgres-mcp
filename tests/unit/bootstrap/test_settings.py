"""Settings / ConfigurationError unit tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from lime_ref_postgres_mcp.bootstrap.settings import ConfigurationError, Settings


def test_from_env_success(full_env: dict[str, str]) -> None:
    settings = Settings.from_env(full_env)
    assert settings.lime_expected_domain == "example.com"
    assert settings.lime_jwks_url.startswith("https://")
    assert settings.lime_expected_aud == "mcp"
    assert settings.lime_jwks_cache_ttl_seconds == 3600
    assert settings.lime_jwt_leeway_seconds == 120
    assert settings.postgres_url.startswith("postgresql://")
    assert settings.agents_policy_path == Path("./config/agents.example.json")
    assert settings.policy_reload_ttl_seconds == 60
    assert settings.pg_statement_timeout == "5s"
    assert settings.pg_lock_timeout == "2s"
    assert settings.pg_idle_in_transaction_timeout == "10s"
    assert settings.pg_max_result_bytes == 1_048_576
    assert settings.pg_pool_min_size == 1
    assert settings.pg_pool_max_size == 4
    assert settings.enable_console_event_sink is True
    assert settings.log_level == "INFO"
    assert settings.log_format == "json"
    assert settings.log_stream == "stderr"
    assert settings.metrics_enabled is True
    assert settings.mcp_bind_host == "127.0.0.1"
    assert settings.mcp_port == 8000


def test_mcp_bind_and_port(full_env: dict[str, str]) -> None:
    full_env["LIME_MCP_BIND_HOST"] = "0.0.0.0"
    full_env["LIME_MCP_PORT"] = "9001"
    settings = Settings.from_env(full_env)
    assert settings.mcp_bind_host == "0.0.0.0"
    assert settings.mcp_port == 9001


def test_mcp_port_out_of_range(full_env: dict[str, str]) -> None:
    full_env["LIME_MCP_PORT"] = "70000"
    with pytest.raises(ConfigurationError, match="LIME_MCP_PORT"):
        Settings.from_env(full_env)


def test_mcp_port_invalid(full_env: dict[str, str]) -> None:
    full_env["LIME_MCP_PORT"] = "nope"
    with pytest.raises(ConfigurationError, match="Invalid integer for LIME_MCP_PORT"):
        Settings.from_env(full_env)


def test_pool_size_defaults(full_env: dict[str, str]) -> None:
    full_env.pop("PG_POOL_MIN_SIZE", None)
    full_env.pop("PG_POOL_MAX_SIZE", None)
    settings = Settings.from_env(full_env)
    assert settings.pg_pool_min_size == 1
    assert settings.pg_pool_max_size == 4


def test_pool_max_less_than_min(full_env: dict[str, str]) -> None:
    full_env["PG_POOL_MIN_SIZE"] = "4"
    full_env["PG_POOL_MAX_SIZE"] = "2"
    with pytest.raises(ConfigurationError, match="PG_POOL_MAX_SIZE"):
        Settings.from_env(full_env)


def test_expected_aud_override(full_env: dict[str, str]) -> None:
    full_env["LIME_EXPECTED_AUD"] = "custom-aud"
    assert Settings.from_env(full_env).lime_expected_aud == "custom-aud"


def test_jwks_ttl_and_leeway(full_env: dict[str, str]) -> None:
    full_env["LIME_JWKS_CACHE_TTL_SECONDS"] = "300"
    full_env["LIME_JWT_VERIFY_LEEWAY_SECONDS"] = "30"
    settings = Settings.from_env(full_env)
    assert settings.lime_jwks_cache_ttl_seconds == 300
    assert settings.lime_jwt_leeway_seconds == 30


def test_domain_normalize_strips_scheme(full_env: dict[str, str]) -> None:
    full_env["LIME_EXPECTED_DOMAIN"] = "https://Example.com"
    assert Settings.from_env(full_env).lime_expected_domain == "example.com"


def test_domain_rejects_port(full_env: dict[str, str]) -> None:
    full_env["LIME_EXPECTED_DOMAIN"] = "example.com:443"
    with pytest.raises(ConfigurationError, match="LIME_EXPECTED_DOMAIN"):
        Settings.from_env(full_env)


def test_log_settings(full_env: dict[str, str]) -> None:
    full_env["LIME_MCP_LOG_LEVEL"] = "DEBUG"
    full_env["LIME_MCP_LOG_FORMAT"] = "console"
    full_env["LIME_MCP_LOG_STREAM"] = "stdout"
    full_env["LIME_MCP_METRICS"] = "0"
    settings = Settings.from_env(full_env)
    assert settings.log_level == "DEBUG"
    assert settings.log_format == "console"
    assert settings.log_stream == "stdout"
    assert settings.metrics_enabled is False


def test_log_format_invalid(full_env: dict[str, str]) -> None:
    full_env["LIME_MCP_LOG_FORMAT"] = "xml"
    with pytest.raises(ConfigurationError, match="LIME_MCP_LOG_FORMAT"):
        Settings.from_env(full_env)


def test_defaults_when_optional_omitted(full_env: dict[str, str]) -> None:
    for key in (
        "AGENTS_POLICY_PATH",
        "POLICY_RELOAD_TTL_SECONDS",
        "PG_STATEMENT_TIMEOUT",
        "PG_LOCK_TIMEOUT",
        "PG_IDLE_IN_TRANSACTION_TIMEOUT",
        "PG_MAX_RESULT_BYTES",
        "ENABLE_CONSOLE_EVENT_SINK",
    ):
        full_env.pop(key, None)
    settings = Settings.from_env(full_env)
    assert settings.agents_policy_path == Path("./config/agents.json")
    assert settings.policy_reload_ttl_seconds == 60
    assert settings.pg_statement_timeout == "5s"
    assert settings.pg_max_result_bytes == 1_048_576
    assert settings.enable_console_event_sink is True


def test_missing_required(full_env: dict[str, str]) -> None:
    del full_env["POSTGRES_URL"]
    with pytest.raises(ConfigurationError, match="POSTGRES_URL") as exc_info:
        Settings.from_env(full_env)
    assert exc_info.value.missing == ("POSTGRES_URL",)


def test_invalid_bool(full_env: dict[str, str]) -> None:
    full_env["ENABLE_CONSOLE_EVENT_SINK"] = "maybe"
    with pytest.raises(ConfigurationError, match="Invalid boolean"):
        Settings.from_env(full_env)


def test_bool_false(full_env: dict[str, str]) -> None:
    full_env["ENABLE_CONSOLE_EVENT_SINK"] = "0"
    assert Settings.from_env(full_env).enable_console_event_sink is False


def test_invalid_int(full_env: dict[str, str]) -> None:
    full_env["PG_MAX_RESULT_BYTES"] = "nope"
    with pytest.raises(ConfigurationError, match="Invalid integer"):
        Settings.from_env(full_env)


def test_non_positive_int(full_env: dict[str, str]) -> None:
    full_env["POLICY_RELOAD_TTL_SECONDS"] = "0"
    with pytest.raises(ConfigurationError, match="must be >= 1"):
        Settings.from_env(full_env)


def test_from_env_reads_os_environ(
    monkeypatch: pytest.MonkeyPatch,
    full_env: dict[str, str],
) -> None:
    for key, value in full_env.items():
        monkeypatch.setenv(key, value)
    settings = Settings.from_env()
    assert settings.lime_expected_domain == "example.com"


def test_empty_timeout_strings_fall_back(full_env: dict[str, str]) -> None:
    full_env["PG_STATEMENT_TIMEOUT"] = "  "
    full_env["PG_LOCK_TIMEOUT"] = ""
    full_env["PG_IDLE_IN_TRANSACTION_TIMEOUT"] = " "
    settings = Settings.from_env(full_env)
    assert settings.pg_statement_timeout == "5s"
    assert settings.pg_lock_timeout == "2s"
    assert settings.pg_idle_in_transaction_timeout == "10s"
