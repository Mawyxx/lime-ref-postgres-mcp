"""LimePassportVerifier — wraps lime_mcp_server.TokenVerifier."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol

from lime_mcp_server import TokenValidationResult, TokenVerifier

from lime_ref_postgres_mcp.application.ports.identity import PassportClaims
from lime_ref_postgres_mcp.bootstrap.observability import log
from lime_ref_postgres_mcp.domain.agent.agent_id import AgentId
from lime_ref_postgres_mcp.domain.common.errors import PassportInvalid, PassportMissing
from lime_ref_postgres_mcp.domain.common.result import Err, Ok, Result


class _TokenVerifierLike(Protocol):
    async def verify_async(self, token: str) -> TokenValidationResult: ...

    def close(self) -> None: ...

    def warmup(self, *, raise_on_failure: bool = False) -> bool: ...


_REASON_RULES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("jwks", "fetch", "unavailable", "http"), "jwks_unavailable"),
    (("signature", "crypto"), "bad_signature"),
    (("audience", "aud"), "aud_mismatch"),
    (("expir",), "token_expired"),
    (("forbidden", "passport_version", "request_id"), "forbidden_claim"),
    (("malformed", "segment", "decode"), "malformed_jwt"),
)


def _reason_code_from_error(error: str | None) -> str:
    text = (error or "").lower()
    if "domain" in text and "missing" in text:
        return "domain_missing"
    if "domain" in text:
        return "domain_mismatch"
    for needles, code in _REASON_RULES:
        if any(n in text for n in needles):
            return code
    return "passport_invalid"


def _aud_as_str(aud: object) -> str | None:
    if isinstance(aud, str):
        return aud
    if isinstance(aud, (list, tuple)) and len(aud) == 1 and isinstance(aud[0], str):
        return aud[0]
    return None


def _exp_as_datetime(exp: object) -> datetime | None:
    if isinstance(exp, (int, float)):
        return datetime.fromtimestamp(float(exp), tz=UTC)
    return None


def _missing() -> Err[PassportMissing]:
    return Err(
        PassportMissing(
            invariant_id="identity.passport_missing",
            message="Authorization Bearer token is missing",
            context={},
        )
    )


def _strip_bearer(bearer_token: str) -> Result[str, PassportMissing]:
    token = bearer_token.strip()
    if not token:
        return _missing()
    parts = token.split(None, 1)
    if parts[0].lower() == "bearer":
        if len(parts) == 1 or not parts[1].strip():
            return _missing()
        return Ok(parts[1].strip())
    return Ok(token)


class LimePassportVerifier:
    """PassportVerifier adapter around LIME MCP TokenVerifier."""

    def __init__(
        self,
        *,
        expected_domain: str,
        base_url: str,
        audience: str = "mcp",
        cache_ttl: int | None = None,
        leeway_seconds: int | None = None,
        token_verifier: _TokenVerifierLike | None = None,
    ) -> None:
        if token_verifier is not None:
            self._tv: _TokenVerifierLike = token_verifier
            self._owns_tv = False
        else:
            self._tv = TokenVerifier(
                expected_domain=expected_domain,
                base_url=base_url,
                audience=audience,
                cache_ttl=cache_ttl,
                leeway_seconds=leeway_seconds,
            )
            self._owns_tv = True

    async def verify(
        self, bearer_token: str
    ) -> Result[PassportClaims, PassportMissing | PassportInvalid]:
        stripped = _strip_bearer(bearer_token)
        if isinstance(stripped, Err):
            log(
                "identity",
                "verify.fail",
                level="WARNING",
                code="passport_missing",
                invariant_id=stripped.error.invariant_id,
            )
            return Err(stripped.error)
        result = await self._tv.verify_async(stripped.value)
        if not result.is_valid or result.claims is None:
            reason = _reason_code_from_error(result.error)
            log(
                "identity",
                "verify.fail",
                level="WARNING",
                code=reason,
                invariant_id="identity.passport_invalid",
            )
            return Err(
                PassportInvalid(
                    invariant_id="identity.passport_invalid",
                    message=result.error or "invalid passport",
                    context={"reason_code": reason},
                )
            )
        claims_result = self._claims_from_sdk(result)
        if isinstance(claims_result, Err):
            code = str(claims_result.error.context.get("reason_code") or "passport_invalid")
            log(
                "identity",
                "verify.fail",
                level="WARNING",
                code=code,
                invariant_id=claims_result.error.invariant_id,
            )
            return Err(claims_result.error)
        log(
            "identity",
            "verify.ok",
            agent_id=str(claims_result.value.agent_id),
            domain=claims_result.value.domain,
        )
        return claims_result

    def _claims_from_sdk(
        self, result: TokenValidationResult
    ) -> Result[PassportClaims, PassportInvalid]:
        claims = result.claims
        assert claims is not None
        agent_id_result = AgentId.parse(claims["sub"])
        if isinstance(agent_id_result, Err):
            return Err(
                PassportInvalid(
                    invariant_id="identity.passport_invalid",
                    message="passport sub is not a valid agent_id",
                    context={"reason_code": "agent_id_invalid"},
                )
            )
        return Ok(
            PassportClaims(
                agent_id=agent_id_result.value,
                domain=result.domain,
                aud=_aud_as_str(claims.get("aud")),
                exp=_exp_as_datetime(claims.get("exp")),
            )
        )

    async def warmup(self, *, raise_on_failure: bool = False) -> bool:
        try:
            ok = self._tv.warmup(raise_on_failure=raise_on_failure)
        except Exception:
            log("identity", "jwks.warmup", level="ERROR", status="fail")
            raise
        status = "ok" if ok else "fail"
        log(
            "identity",
            "jwks.warmup",
            level="INFO" if ok else "WARNING",
            status=status,
        )
        return ok

    def close(self) -> None:
        if self._owns_tv:
            self._tv.close()


__all__ = ["LimePassportVerifier"]
