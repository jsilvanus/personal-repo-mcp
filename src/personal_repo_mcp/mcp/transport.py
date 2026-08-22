from __future__ import annotations

from collections.abc import Callable

from starlette.types import ASGIApp, Receive, Scope, Send


class BearerAuthMiddleware:
    """Minimal bearer authentication for a privately deployed MCP endpoint.

    This is intentionally an HTTP boundary around the MCP application. MCP
    protocol messages are left untouched. A later phase can replace this
    policy with richer authorization without changing MCP tool semantics.
    """

    def __init__(self, app: ASGIApp, token: str, *, health_path: str = "/healthz") -> None:
        self.app = app
        self.token = token
        self.health_path = health_path

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("path") == self.health_path:
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        raw_authorization = headers.get(b"authorization", b"").decode("latin-1")
        scheme, _, supplied = raw_authorization.partition(" ")
        if scheme.lower() != "bearer" or not supplied or not _constant_time_equal(supplied, self.token):
            await _send_unauthorized(send)
            return

        await self.app(scope, receive, send)


def _constant_time_equal(left: str, right: str) -> bool:
    import hmac

    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))


async def _send_unauthorized(send: Send) -> None:
    body = b"Unauthorized"
    await send(
        {
            "type": "http.response.start",
            "status": 401,
            "headers": [
                (b"content-type", b"text/plain; charset=utf-8"),
                (b"www-authenticate", b"Bearer"),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})
