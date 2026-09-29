"""A small in-process fake OIDC provider (authentik-like issuer URL with a trailing slash).

Served to the app through an httpx2 ASGI transport; the test "browser" reaches it the same way.
Serves discovery, /jwks, /authorize (302 back with code + state), /token and /userinfo, and signs
RS256 ID tokens with joserfc.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlencode

from joserfc import jwt
from joserfc.jwk import KeySet, RSAKey
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse, Response
from starlette.routing import Route

ISSUER = "http://idp.test/application/o/personal-repo/"
BASE = "/application/o/personal-repo"


@dataclass
class FakeIdp:
    client_id: str = "repo-client"
    client_secret: str | None = "idp-secret"
    subject: str = "user-123"
    claims: dict[str, Any] = field(default_factory=lambda: {"name": "Test User", "preferred_username": "tester"})
    userinfo: dict[str, Any] = field(default_factory=lambda: {"email": "tester@example.org", "email_verified": True})
    nonce_override: str | None = None
    audience_override: str | None = None
    authorize_error: str | None = None
    discovery_down: bool = False
    key: RSAKey = field(default_factory=lambda: RSAKey.generate_key(2048, parameters={"kid": "k1", "use": "sig", "alg": "RS256"}))
    pending: dict[str, dict[str, str]] = field(default_factory=dict)
    token_requests: list[dict[str, str]] = field(default_factory=list)
    authorize_requests: list[dict[str, str]] = field(default_factory=list)

    def app(self) -> Starlette:
        async def discovery(_request: Request) -> Response:
            if self.discovery_down:
                return Response("down", status_code=503)
            return JSONResponse({
                "issuer": ISSUER,
                "authorization_endpoint": "http://idp.test" + BASE + "/authorize/",
                "token_endpoint": "http://idp.test" + BASE + "/token/",
                "userinfo_endpoint": "http://idp.test" + BASE + "/userinfo/",
                "jwks_uri": "http://idp.test" + BASE + "/jwks/",
                "id_token_signing_alg_values_supported": ["RS256"],
                "response_types_supported": ["code"],
                "subject_types_supported": ["public"],
            })

        async def jwks(_request: Request) -> Response:
            return JSONResponse(KeySet([self.key]).as_dict(private=False))

        async def authorize(request: Request) -> Response:
            q = dict(request.query_params)
            self.authorize_requests.append(q)
            if self.authorize_error:
                return RedirectResponse(q["redirect_uri"] + "?" + urlencode({"error": self.authorize_error, "state": q["state"]}), 302)
            assert q["response_type"] == "code" and q["client_id"] == self.client_id
            assert q["code_challenge_method"] == "S256" and "openid" in q["scope"].split()
            code = secrets.token_urlsafe(16)
            self.pending[code] = q
            return RedirectResponse(q["redirect_uri"] + "?" + urlencode({"code": code, "state": q["state"]}), 302)

        async def token(request: Request) -> Response:
            form = {k: v for k, v in (await request.form()).items()}
            self.token_requests.append(form)
            auth = request.headers.get("authorization", "")
            if self.client_secret:
                expected = "Basic " + base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
                if auth != expected:
                    return JSONResponse({"error": "invalid_client"}, 401)
            elif auth or form.get("client_id") != self.client_id:
                return JSONResponse({"error": "invalid_client"}, 401)
            q = self.pending.pop(form.get("code", ""), None)
            if q is None or form.get("grant_type") != "authorization_code" or form.get("redirect_uri") != q["redirect_uri"]:
                return JSONResponse({"error": "invalid_grant"}, 400)
            digest = base64.urlsafe_b64encode(hashlib.sha256(form.get("code_verifier", "").encode()).digest()).rstrip(b"=").decode()
            if digest != q["code_challenge"]:
                return JSONResponse({"error": "invalid_grant"}, 400)
            now = int(time.time())
            id_claims = {
                "iss": ISSUER,
                "sub": self.subject,
                "aud": self.audience_override or self.client_id,
                "iat": now,
                "exp": now + 300,
                "nonce": self.nonce_override or q["nonce"],
                **self.claims,
            }
            id_token = jwt.encode({"alg": "RS256", "kid": "k1"}, id_claims, self.key)
            return JSONResponse({"access_token": "idp-at-" + secrets.token_urlsafe(8), "token_type": "Bearer", "expires_in": 300, "id_token": id_token})

        async def userinfo(request: Request) -> Response:
            if not request.headers.get("authorization", "").startswith("Bearer idp-at-"):
                return JSONResponse({"error": "invalid_token"}, 401)
            return JSONResponse({"sub": self.subject, **self.userinfo})

        return Starlette(routes=[
            Route(BASE + "/.well-known/openid-configuration", discovery),
            Route(BASE + "/jwks/", jwks),
            Route(BASE + "/authorize/", authorize),
            Route(BASE + "/token/", token, methods=["POST"]),
            Route(BASE + "/userinfo/", userinfo),
        ])
