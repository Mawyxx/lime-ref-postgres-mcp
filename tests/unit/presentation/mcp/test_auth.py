"""extract_bearer unit tests."""

from __future__ import annotations

from lime_ref_postgres_mcp.presentation.mcp.auth import extract_bearer


def test_bearer_ok() -> None:
    assert extract_bearer({"Authorization": "Bearer tok"}) == "tok"


def test_bearer_case_insensitive_header() -> None:
    assert extract_bearer({"authorization": "Bearer abc"}) == "abc"


def test_bearer_scheme_case_insensitive() -> None:
    assert extract_bearer({"Authorization": "bearer xyz"}) == "xyz"


def test_missing_header() -> None:
    assert extract_bearer({}) is None


def test_empty_token() -> None:
    assert extract_bearer({"Authorization": "Bearer "}) is None
    assert extract_bearer({"Authorization": "Bearer   "}) is None


def test_non_bearer_scheme() -> None:
    assert extract_bearer({"Authorization": "Basic abc"}) is None


def test_malformed() -> None:
    assert extract_bearer({"Authorization": "Bearer"}) is None
    assert extract_bearer({"Authorization": "tok"}) is None


def test_request_like_headers() -> None:
    class _Req:
        def __init__(self) -> None:
            self.headers = {"Authorization": "Bearer from-req"}

    assert extract_bearer(_Req()) == "from-req"


def test_starlette_request_uses_headers_not_mapping() -> None:
    from starlette.requests import Request

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/mcp",
        "raw_path": b"/mcp",
        "query_string": b"",
        "headers": [(b"authorization", b"Bearer starlette-tok")],
        "client": ("127.0.0.1", 123),
        "server": ("127.0.0.1", 80),
    }
    assert extract_bearer(Request(scope)) == "starlette-tok"


def test_upper_case_header_key_on_dict() -> None:
    assert extract_bearer({"AUTHORIZATION": "Bearer upper"}) == "upper"


def test_items_fallback_when_get_blind() -> None:
    class _Blind(dict[str, str]):
        def get(self, key: object, default: object = None) -> object:  # noqa: ANN001
            return None

    assert extract_bearer(_Blind({"Authorization": "Bearer via-items"})) == "via-items"


def test_non_string_header_values_ignored() -> None:
    assert extract_bearer({"Authorization": 123}) is None  # type: ignore[dict-item]


def test_non_mapping_blind_get_returns_none() -> None:
    class _NotMap:
        def get(self, key: object, default: object = None) -> object:  # noqa: ANN001
            return 1  # non-str for every candidate

    assert extract_bearer(_NotMap()) is None


def test_object_without_get_returns_none() -> None:
    class _Empty:
        pass

    assert extract_bearer(_Empty()) is None
