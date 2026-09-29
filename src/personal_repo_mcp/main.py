from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Mount, Route

from .config import Settings, load_settings
from .mcp.server import create_mcp, transport_security
from .mcp.transport import BearerAuthMiddleware
from .repositories import RepositoryManager


OAUTH_PUBLIC_PATHS = (
    "/.well-known/oauth-protected-resource",
    "/.well-known/oauth-authorization-server",
    "/.well-known/openid-configuration",
    "/oauth/",
    "/oidc/",
)


def create_app(settings: Settings | None = None, *, oauth_options: dict[str, Any] | None = None) -> Starlette:
    """Build the HTTP application without starting the process.

    ``oauth_options`` is for tests: ``oidc_transport`` (an httpx2 transport to a fake
    IdP) and ``fetch_client_metadata`` (a CIMD stub). It is ignored when OAuth is off.
    """
    settings = settings or load_settings()
    repositories = RepositoryManager(
        settings.repository_root,
        settings.repositories,
        settings.repository_patterns,
        backend=settings.git_backend,
    )
    mcp = create_mcp(settings, repositories)
    mcp_app = mcp.streamable_http_app(
        stateless_http=True,
        json_response=True,
        streamable_http_path="/",
        transport_security=transport_security(settings),
    )

    async def healthz(_request):
        return PlainTextResponse("ok")

    routes: list = [Route("/healthz", healthz, methods=["GET"])]
    auth_options: dict[str, Any] = {}
    store = None
    if settings.oauth is not None:
        from .oauth.oidc import OidcClient
        from .oauth.server import AuthorizationServer
        from .oauth.store import OAuthStore

        options = oauth_options or {}
        store = OAuthStore(settings.oauth.database_path)
        authorization_server = AuthorizationServer(
            settings.oauth,
            store,
            OidcClient(settings.oauth, transport=options.get("oidc_transport")),
            fetch_client_metadata=options.get("fetch_client_metadata"),
        )
        routes.extend(authorization_server.routes())

        async def verify_access_token(token: str) -> dict[str, Any] | None:
            return authorization_server.signer.verify_access_token(token)

        auth_options = {
            "verifier": verify_access_token,
            "public_paths": OAUTH_PUBLIC_PATHS,
            "resource_metadata_url": authorization_server.resource_metadata_url,
        }
    routes.append(Mount("/mcp", app=mcp_app))

    @asynccontextmanager
    async def lifespan(_app: Starlette) -> AsyncIterator[None]:
        try:
            async with mcp.session_manager.run():
                yield
        finally:
            repositories.close()
            if store is not None:
                store.close()

    app = Starlette(routes=routes, lifespan=lifespan)
    app.add_middleware(BearerAuthMiddleware, token=settings.token or "", **auth_options)
    return app


def main() -> None:
    settings = load_settings()
    app = create_app(settings)

    import uvicorn

    uvicorn.run(app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
