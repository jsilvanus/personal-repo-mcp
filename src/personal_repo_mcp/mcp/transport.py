from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any

from starlette.types import ASGIApp, Receive, Scope, Send

TokenVerifier = Callable[[str], Awaitable[dict[str, Any] | None]]


class BearerAuthMiddleware:
    """Bearer authentication for a privately deployed MCP endpoint.

    This is intentionally an HTTP boundary around the MCP application. MCP
    protocol messages are left untouched. The static token always works. When
    OAuth is enabled (OIDC_ISSUER set), OAuth access tokens are accepted too via
    ``verifier``, the OAuth/OIDC endpoints in ``public_paths`` bypass the check,
    and 401 responses carry the RFC 9728 ``resource_metadata`` challenge.
    """

    def __init__(
        self,
        app: ASGIApp,
        token: str,
        *,
        health_path: str = "/healthz",
        verifier: TokenVerifier | None = None,
        public_paths: tuple[str, ...] = (),
        resource_metadata_url: str | None = None,
    ) -> None:
        self.app = app
        self.token = token
        self.health_path = health_path
        self.verifier = verifier
        self.public_paths = public_paths
        self.resource_metadata_url = resource_metadata_url

    def _is_public(self, path: str) -> bool:
        return any(path == prefix.rstrip("/") or path.startswith(prefix) for prefix in self.public_paths)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        if scope["type"] != "http" or path == self.health_path or self._is_public(path):
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        raw_authorization = headers.get(b"authorization", b"").decode("latin-1")
        scheme, _, supplied = raw_authorization.partition(" ")
        if scheme.lower() == "bearer" and supplied:
            if self.token and _constant_time_equal(supplied, self.token):
                await self.app(scope, receive, send)
                return
            if self.verifier is not None:
                claims = await self.verifier(supplied)
                if claims is not None:
                    # Available to handlers as request.state.oauth_claims.
                    scope.setdefault("state", {})["oauth_claims"] = claims
                    await self.app(scope, receive, send)
                    return
            await self._unauthorized(send, error="invalid_token")
            return

        await self._unauthorized(send)

    async def _unauthorized(self, send: Send, *, error: str | None = None) -> None:
        if self.resource_metadata_url is None:
            await _send_unauthorized(send)
            return
        challenge = f'Bearer resource_metadata="{self.resource_metadata_url}", scope="mcp"'
        if error:
            challenge += f', error="{error}", error_description="The access token is missing, expired or invalid."'
        body = json.dumps({"error": error or "unauthorized"}).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": 401,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"www-authenticate", challenge.encode("latin-1")),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})


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
