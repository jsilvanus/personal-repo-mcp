from __future__ import annotations

from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Mount, Route

from .config import Settings, load_settings
from .mcp.server import create_mcp
from .mcp.transport import BearerAuthMiddleware
from .repositories import RepositoryManager


def create_app(settings: Settings | None = None) -> Starlette:
    """Build the HTTP application without starting the process."""
    settings = settings or load_settings()
    repositories = RepositoryManager(settings.repositories)
    mcp = create_mcp(settings, repositories)
    mcp_app = mcp.streamable_http_app()

    async def healthz(_request):
        return PlainTextResponse("ok")

    app = Starlette(
        routes=[
            Route("/healthz", healthz, methods=["GET"]),
            Mount("/mcp", app=mcp_app),
        ]
    )
    app.add_middleware(BearerAuthMiddleware, token=settings.token or "")
    return app


def main() -> None:
    settings = load_settings()
    app = create_app(settings)

    import uvicorn

    uvicorn.run(app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
