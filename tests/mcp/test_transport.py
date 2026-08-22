import httpx
import pytest

from personal_repo_mcp.mcp.transport import BearerAuthMiddleware


async def _app(scope, receive, send):
    await send({
        "type": "http.response.start",
        "status": 200,
        "headers": [(b"content-type", b"text/plain")],
    })
    await send({"type": "http.response.body", "body": b"ok"})


def test_bearer_auth_rejects_missing_token() -> None:
    async def run() -> None:
        app = BearerAuthMiddleware(_app, "secret")
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/mcp")
            assert response.status_code == 401

    import asyncio

    asyncio.run(run())


@pytest.mark.asyncio
async def test_bearer_auth_accepts_valid_token() -> None:
    app = BearerAuthMiddleware(_app, "secret")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/mcp", headers={"Authorization": "Bearer secret"})
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_health_path_bypasses_auth() -> None:
    app = BearerAuthMiddleware(_app, "secret", health_path="/healthz")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/healthz")
    assert response.status_code == 200
