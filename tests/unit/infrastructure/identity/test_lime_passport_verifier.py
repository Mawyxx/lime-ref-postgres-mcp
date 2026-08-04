"""LimePassportVerifier unit tests (V-1..V-10) + base_url."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from lime_mcp_server import TokenValidationResult
from lime_mcp_server._claims import McpAccessTokenClaims

from lime_ref_postgres_mcp.bootstrap.container import create_passport_verifier
from lime_ref_postgres_mcp.bootstrap.settings import ConfigurationError, Settings
from lime_ref_postgres_mcp.domain.common.errors import PassportInvalid, PassportMissing
from lime_ref_postgres_mcp.domain.common.result import Err, Ok
from lime_ref_postgres_mcp.infrastructure.identity.lime_base_url import base_url_from_jwks_url
from lime_ref_postgres_mcp.infrastructure.identity.lime_passport_verifier import (
    LimePassportVerifier,
)


def _claims(**overrides: object) -> McpAccessTokenClaims:
    base: McpAccessTokenClaims = {
        "sub": "agent_ok",
        "iss": "https://lime.pics",
        "aud": "mcp",
        "iat": 1_700_000_000,
        "exp": 1_900_000_000,
        "jti": "jti-1",
        "domain": "example.com",
    }
    base.update(overrides)  # type: ignore[typeddict-item]
    return base


class FakeTokenVerifier:
    def __init__(self) -> None:
        self.calls = 0
        self.next_result: TokenValidationResult = TokenValidationResult(
            is_valid=True,
            claims=_claims(),
            error=None,
        )

    async def verify_async(self, token: str) -> TokenValidationResult:
        self.calls += 1
        return self.next_result

    def close(self) -> None:
        return None

    def warmup(self, *, raise_on_failure: bool = False) -> bool:
        return True


def _verifier(
    fake: FakeTokenVerifier | None = None,
) -> tuple[LimePassportVerifier, FakeTokenVerifier]:
    tv = fake or FakeTokenVerifier()
    return (
        LimePassportVerifier(
            expected_domain="example.com",
            base_url="https://lime.pics",
            token_verifier=tv,
        ),
        tv,
    )


@pytest.mark.asyncio
async def test_v1_blank_token() -> None:
    verifier, tv = _verifier()
    result = await verifier.verify("   ")
    assert isinstance(result, Err)
    assert isinstance(result.error, PassportMissing)
    assert tv.calls == 0


@pytest.mark.asyncio
async def test_v1b_bearer_prefix_only() -> None:
    verifier, tv = _verifier()
    result = await verifier.verify("Bearer ")
    assert isinstance(result, Err)
    assert isinstance(result.error, PassportMissing)
    assert tv.calls == 0


@pytest.mark.asyncio
async def test_v2_sdk_invalid_malformed() -> None:
    fake = FakeTokenVerifier()
    fake.next_result = TokenValidationResult(
        is_valid=False, claims=None, error="malformed JWT segments"
    )
    verifier, _ = _verifier(fake)
    result = await verifier.verify("not.a.jwt")
    assert isinstance(result, Err)
    assert isinstance(result.error, PassportInvalid)
    assert result.error.context.get("reason_code") == "malformed_jwt"


@pytest.mark.asyncio
async def test_v2b_bad_signature() -> None:
    fake = FakeTokenVerifier()
    fake.next_result = TokenValidationResult(is_valid=False, claims=None, error="bad signature")
    verifier, _ = _verifier(fake)
    result = await verifier.verify("tok")
    assert isinstance(result, Err)
    assert result.error.context.get("reason_code") == "bad_signature"


@pytest.mark.asyncio
async def test_v2c_generic_invalid_and_null_error() -> None:
    fake = FakeTokenVerifier()
    fake.next_result = TokenValidationResult(is_valid=False, claims=None, error=None)
    verifier, _ = _verifier(fake)
    result = await verifier.verify("tok")
    assert isinstance(result, Err)
    assert result.error.message == "invalid passport"
    assert result.error.context.get("reason_code") == "passport_invalid"


@pytest.mark.asyncio
async def test_v3_aud_mismatch() -> None:
    fake = FakeTokenVerifier()
    fake.next_result = TokenValidationResult(is_valid=False, claims=None, error="audience mismatch")
    verifier, _ = _verifier(fake)
    result = await verifier.verify("tok")
    assert isinstance(result, Err)
    assert result.error.context.get("reason_code") == "aud_mismatch"


@pytest.mark.asyncio
async def test_v4_domain_missing() -> None:
    fake = FakeTokenVerifier()
    fake.next_result = TokenValidationResult(
        is_valid=False, claims=None, error="domain claim missing"
    )
    verifier, _ = _verifier(fake)
    result = await verifier.verify("tok")
    assert isinstance(result, Err)
    assert result.error.context.get("reason_code") == "domain_missing"


@pytest.mark.asyncio
async def test_v4b_domain_mismatch() -> None:
    fake = FakeTokenVerifier()
    fake.next_result = TokenValidationResult(
        is_valid=False, claims=None, error="domain pin mismatch"
    )
    verifier, _ = _verifier(fake)
    result = await verifier.verify("tok")
    assert isinstance(result, Err)
    assert result.error.context.get("reason_code") == "domain_mismatch"


@pytest.mark.asyncio
async def test_v5_expired() -> None:
    fake = FakeTokenVerifier()
    fake.next_result = TokenValidationResult(is_valid=False, claims=None, error="token expired")
    verifier, _ = _verifier(fake)
    result = await verifier.verify("tok")
    assert isinstance(result, Err)
    assert result.error.context.get("reason_code") == "token_expired"


@pytest.mark.asyncio
async def test_v6_forbidden_claim() -> None:
    fake = FakeTokenVerifier()
    fake.next_result = TokenValidationResult(
        is_valid=False, claims=None, error="forbidden claim passport_version"
    )
    verifier, _ = _verifier(fake)
    result = await verifier.verify("tok")
    assert isinstance(result, Err)
    assert result.error.context.get("reason_code") == "forbidden_claim"


@pytest.mark.asyncio
async def test_v7_happy_claims_map() -> None:
    verifier, tv = _verifier()
    result = await verifier.verify("Bearer eyJ.valid.token")
    assert isinstance(result, Ok)
    assert result.value.agent_id.value == "agent_ok"
    assert result.value.domain == "example.com"
    assert result.value.aud == "mcp"
    assert result.value.exp == datetime.fromtimestamp(1_900_000_000, tz=UTC)
    assert tv.calls == 1


@pytest.mark.asyncio
async def test_v7b_aud_list_and_non_numeric_exp() -> None:
    fake = FakeTokenVerifier()
    claims = _claims()
    claims["aud"] = ["mcp"]  # type: ignore[typeddict-item]
    claims["exp"] = "nope"  # type: ignore[typeddict-item]
    fake.next_result = TokenValidationResult(is_valid=True, claims=claims, error=None)
    verifier, _ = _verifier(fake)
    result = await verifier.verify("tok")
    assert isinstance(result, Ok)
    assert result.value.aud == "mcp"
    assert result.value.exp is None


@pytest.mark.asyncio
async def test_v7c_aud_multi_list_returns_none() -> None:
    fake = FakeTokenVerifier()
    claims = _claims()
    claims["aud"] = ["mcp", "other"]  # type: ignore[typeddict-item]
    fake.next_result = TokenValidationResult(is_valid=True, claims=claims, error=None)
    verifier, _ = _verifier(fake)
    result = await verifier.verify("tok")
    assert isinstance(result, Ok)
    assert result.value.aud is None


@pytest.mark.asyncio
async def test_v7d_valid_flag_without_claims() -> None:
    fake = FakeTokenVerifier()
    fake.next_result = TokenValidationResult(is_valid=True, claims=None, error=None)
    verifier, _ = _verifier(fake)
    result = await verifier.verify("tok")
    assert isinstance(result, Err)
    assert result.error.context.get("reason_code") == "passport_invalid"


@pytest.mark.asyncio
async def test_owned_token_verifier_close() -> None:
    verifier = LimePassportVerifier(
        expected_domain="example.com",
        base_url="https://lime.pics",
        audience="mcp",
        cache_ttl=3600,
        leeway_seconds=120,
    )
    verifier.close()


@pytest.mark.asyncio
async def test_v8_second_verify_no_extra_fetch() -> None:
    verifier, tv = _verifier()
    assert isinstance(await verifier.verify("tok1"), Ok)
    assert isinstance(await verifier.verify("tok2"), Ok)
    assert tv.calls == 2


@pytest.mark.asyncio
async def test_v9_agent_id_invalid() -> None:
    fake = FakeTokenVerifier()
    fake.next_result = TokenValidationResult(
        is_valid=True,
        claims=_claims(sub="   "),
        error=None,
    )
    verifier, _ = _verifier(fake)
    result = await verifier.verify("tok")
    assert isinstance(result, Err)
    assert result.error.context.get("reason_code") == "agent_id_invalid"


@pytest.mark.asyncio
async def test_v10_jwks_unavailable() -> None:
    fake = FakeTokenVerifier()
    fake.next_result = TokenValidationResult(
        is_valid=False, claims=None, error="JWKS fetch unavailable"
    )
    verifier, _ = _verifier(fake)
    result = await verifier.verify("tok")
    assert isinstance(result, Err)
    assert result.error.context.get("reason_code") == "jwks_unavailable"


@pytest.mark.asyncio
async def test_warmup_and_close_delegate() -> None:
    fake = FakeTokenVerifier()
    verifier, _ = _verifier(fake)
    assert await verifier.warmup() is True
    verifier.close()


@pytest.mark.asyncio
async def test_warmup_failure_logs_and_reraises() -> None:
    class BoomTv(FakeTokenVerifier):
        def warmup(self, *, raise_on_failure: bool = False) -> bool:
            raise RuntimeError("jwks boom")

    verifier, _ = _verifier(BoomTv())
    with pytest.raises(RuntimeError, match="jwks boom"):
        await verifier.warmup(raise_on_failure=True)


@pytest.mark.asyncio
async def test_warmup_returns_false() -> None:
    class FailTv(FakeTokenVerifier):
        def warmup(self, *, raise_on_failure: bool = False) -> bool:
            return False

    verifier, _ = _verifier(FailTv())
    assert await verifier.warmup() is False


def test_base_url_from_jwks() -> None:
    assert base_url_from_jwks_url("https://lime.pics/.well-known/jwks.json") == "https://lime.pics"
    assert base_url_from_jwks_url("https://lime.pics/") == "https://lime.pics"
    assert base_url_from_jwks_url("https://lime.pics") == "https://lime.pics"


def test_base_url_rejects_bad() -> None:
    with pytest.raises(ValueError):
        base_url_from_jwks_url("")
    with pytest.raises(ValueError):
        base_url_from_jwks_url("not-a-url")
    with pytest.raises(ValueError):
        base_url_from_jwks_url("https://lime.pics/other/path")


def test_create_passport_verifier_maps_bad_jwks_url() -> None:
    settings = Settings(
        lime_expected_domain="example.com",
        lime_jwks_url="https://lime.pics/bad",
        lime_expected_aud="mcp",
        lime_jwks_cache_ttl_seconds=3600,
        lime_jwt_leeway_seconds=120,
        agents_policy_path=Path("."),
        policy_reload_ttl_seconds=60,
        postgres_url="postgresql://x",
        pg_statement_timeout="5s",
        pg_lock_timeout="2s",
        pg_idle_in_transaction_timeout="10s",
        pg_max_result_bytes=1,
        pg_pool_min_size=1,
        pg_pool_max_size=4,
        enable_console_event_sink=True,
        log_level="INFO",
        log_format="json",
        log_stream="stderr",
        metrics_enabled=True,
        mcp_bind_host="127.0.0.1",
        mcp_port=8000,
    )
    with pytest.raises(ConfigurationError):
        create_passport_verifier(settings)
