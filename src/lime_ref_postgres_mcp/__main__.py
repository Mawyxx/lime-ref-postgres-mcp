"""CLI entry — composition smoke (default) or ``serve`` Streamable HTTP."""

from __future__ import annotations

import sys

import uvicorn

from lime_ref_postgres_mcp.bootstrap.container import build_scaffold_runtime
from lime_ref_postgres_mcp.bootstrap.observability import log
from lime_ref_postgres_mcp.bootstrap.settings import ConfigurationError
from lime_ref_postgres_mcp.presentation.mcp.server import build_asgi_app


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] == "serve":
        return _serve()
    return _smoke()


def _smoke() -> int:
    try:
        build_scaffold_runtime()
    except ConfigurationError as exc:
        log("serve", "config.error", level="ERROR", message=exc.message)
        return 1
    log(
        "serve",
        "composition.ok",
        detail="identity, policy, and database adapters; no transport; database connection lazy",
    )
    return 0


def _serve() -> int:
    try:
        runtime = build_scaffold_runtime()
    except ConfigurationError as exc:
        log("serve", "config.error", level="ERROR", message=exc.message)
        return 1
    _server, app = build_asgi_app(runtime)
    host = runtime.settings.mcp_bind_host
    port = runtime.settings.mcp_port
    log("serve", "serve.start", host=host, port=port, path="/mcp")
    try:
        uvicorn.run(app, host=host, port=port, log_level="info")
    finally:
        log("serve", "serve.stop", host=host, port=port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
