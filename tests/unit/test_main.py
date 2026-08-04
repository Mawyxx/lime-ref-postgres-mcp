"""__main__ entry tests."""

from __future__ import annotations

import json
from typing import Any

import pytest

from lime_ref_postgres_mcp.__main__ import main
from lime_ref_postgres_mcp.bootstrap.container import (
    create_database,
    create_passport_verifier,
    create_policy_store,
)
from lime_ref_postgres_mcp.bootstrap.settings import Settings
from lime_ref_postgres_mcp.infrastructure.clock.system_clock import SystemClock
from lime_ref_postgres_mcp.infrastructure.identity.lime_passport_verifier import (
    LimePassportVerifier,
)
from lime_ref_postgres_mcp.infrastructure.policy.json_agent_policy_store import (
    JsonAgentPolicyStore,
)
from lime_ref_postgres_mcp.infrastructure.postgres.asyncpg_database_gateway import (
    AsyncpgDatabaseGateway,
)


def _json_lines(text: str) -> list[dict[str, object]]:
    lines = [ln for ln in text.splitlines() if ln.strip()]
    return [json.loads(ln) for ln in lines]


def test_main_ok(
    monkeypatch: pytest.MonkeyPatch,
    full_env: dict[str, str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    for key, value in full_env.items():
        monkeypatch.setenv(key, value)
    assert main([]) == 0
    err = capsys.readouterr().err
    records = _json_lines(err)
    assert any(r.get("event") == "composition.ok" for r in records)
    assert "database connection lazy" in err


def test_main_config_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.delenv("LIME_EXPECTED_DOMAIN", raising=False)
    monkeypatch.delenv("LIME_JWKS_URL", raising=False)
    monkeypatch.delenv("POSTGRES_URL", raising=False)
    assert main([]) == 1
    err = capsys.readouterr().err
    records = _json_lines(err)
    assert any(r.get("event") == "config.error" for r in records)


def test_serve_wires_uvicorn(
    monkeypatch: pytest.MonkeyPatch,
    full_env: dict[str, str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    for key, value in full_env.items():
        monkeypatch.setenv(key, value)
    full_env_port = {"LIME_MCP_PORT": "8765", "LIME_MCP_BIND_HOST": "127.0.0.1"}
    for key, value in full_env_port.items():
        monkeypatch.setenv(key, value)

    called: dict[str, Any] = {}

    def fake_run(app: object, **kwargs: object) -> None:
        called["app"] = app
        called["kwargs"] = kwargs

    monkeypatch.setattr("lime_ref_postgres_mcp.__main__.uvicorn.run", fake_run)
    assert main(["serve"]) == 0
    assert called["kwargs"]["host"] == "127.0.0.1"
    assert called["kwargs"]["port"] == 8765
    err = capsys.readouterr().err
    records = _json_lines(err)
    assert any(r.get("event") == "serve.start" for r in records)
    assert any(r.get("event") == "serve.stop" for r in records)
    assert called["app"] is not None


def test_serve_config_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.delenv("POSTGRES_URL", raising=False)
    monkeypatch.delenv("LIME_EXPECTED_DOMAIN", raising=False)
    monkeypatch.delenv("LIME_JWKS_URL", raising=False)
    assert main(["serve"]) == 1
    err = capsys.readouterr().err
    records = _json_lines(err)
    assert any(r.get("event") == "config.error" for r in records)


def test_factories(settings: Settings) -> None:
    clock = SystemClock()
    verifier = create_passport_verifier(settings)
    store = create_policy_store(settings, clock)
    database = create_database(settings)
    assert isinstance(verifier, LimePassportVerifier)
    assert isinstance(store, JsonAgentPolicyStore)
    assert isinstance(database, AsyncpgDatabaseGateway)
    assert database._pool is None
    verifier.close()
