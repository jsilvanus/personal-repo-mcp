"""Embedded OAuth authorization server whose sign-in step is OIDC only.

Ported from the codestash `mcp/api-connector-style` scaffold: CIMD client ids, S256 PKCE,
`/oauth/authorize` + `/oauth/token`, refresh tokens and HS256 JWT access tokens bound to
iss = public URL and aud = `<public URL>/mcp`. The password step of the scaffold is replaced
by `/oidc/login` -> IdP -> `/oidc/callback` -> consent.
"""

from __future__ import annotations

import base64
import hmac
import logging
import threading
import time
from collections import deque
from collections.abc import Awaitable, Callable
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse, Response
from starlette.routing import Route

from ..audit.logger import AuditLogger
from ..config import OAuthSettings
from .cimd import CimdMetadata, fetch_cimd_metadata, is_cimd_client_id
from .oidc import OidcClient, OidcError
from .pages import consent_page, error_page, invalid_request_page
from .store import AuthorizationCode, OAuthStore, OidcLoginState, RefreshToken
from .tokens import TokenSigner, random_token, verify_s256

LOGGER = logging.getLogger("personal_repo_mcp.oauth")
AUDIT = AuditLogger(logging.getLogger("personal_repo_mcp.audit"))

COOKIE_NAME = "personal_repo_mcp_oidc"
COOKIE_PATH = "/oidc"
STATE_TTL = 600
CODE_TTL = 60
REFRESH_TOKEN_TTL = 30 * 86_400
SCOPE = "mcp"

FetchClientMetadata = Callable[[str], Awaitable[CimdMetadata]]


class RateLimiter:
    """In-memory sliding-window limit per client IP (the repo has no shared limiter)."""

    def __init__(self, limit: int = 30, window: float = 60.0) -> None:
        self.limit = limit
        self.window = window
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            if len(self._hits) > 10_000:
                self._hits = {k: v for k, v in self._hits.items() if v and v[-1] > now - self.window}
            hits = self._hits.setdefault(key, deque())
            while hits and hits[0] <= now - self.window:
                hits.popleft()
            if len(hits) >= self.limit:
                return False
            hits.append(now)
            return True


def encode_oauth(params: dict[str, str]) -> str:
    return base64.urlsafe_b64encode(urlencode(params).encode("utf-8")).rstrip(b"=").decode("ascii")


def decode_oauth(value: str) -> dict[str, str]:
    padded = value + "=" * (-len(value) % 4)
    return dict(parse_qsl(base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8"), keep_blank_values=True))


def _with_query(uri: str, params: dict[str, str]) -> str:
    parsed = urlparse(uri)
    query = parse_qsl(parsed.query, keep_blank_values=True) + list(params.items())
    return urlunparse(parsed._replace(query=urlencode(query)))


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


class AuthorizationServer:
    def __init__(
        self,
        settings: OAuthSettings,
        store: OAuthStore,
        oidc: OidcClient,
        *,
        fetch_client_metadata: FetchClientMetadata | None = None,
        rate_limiter: RateLimiter | None = None,
    ) -> None:
        self.settings = settings
        self.store = store
        self.oidc = oidc
        self.signer = TokenSigner(settings.jwt_secret, settings.public_url, settings.resource)
        self.fetch_client_metadata = fetch_client_metadata or fetch_cimd_metadata
        self.rate_limiter = rate_limiter or RateLimiter()

    # Metadata -------------------------------------------------------------

    def authorization_server_metadata(self) -> dict:
        url = self.settings.public_url
        return {
            "issuer": url,
            "authorization_endpoint": url + "/oauth/authorize",
            "token_endpoint": url + "/oauth/token",
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "code_challenge_methods_supported": ["S256"],
            "token_endpoint_auth_methods_supported": ["none"],
            "scopes_supported": [SCOPE],
            "client_id_metadata_document_supported": True,
            "authorization_response_iss_parameter_supported": True,
        }

    def protected_resource_metadata(self) -> dict:
        return {
            "resource": self.settings.resource,
            "authorization_servers": [self.settings.public_url],
            "scopes_supported": [SCOPE],
            "bearer_methods_supported": ["header"],
        }

    @property
    def resource_metadata_url(self) -> str:
        return self.settings.public_url + "/.well-known/oauth-protected-resource/mcp"

    def routes(self) -> list[Route]:
        async def as_metadata(_request: Request) -> Response:
            return JSONResponse(self.authorization_server_metadata())

        async def pr_metadata(_request: Request) -> Response:
            return JSONResponse(self.protected_resource_metadata())

        return [
            # RFC 9728 path-inserted URL for resource <public URL>/mcp; the root URL stays for older clients.
            Route("/.well-known/oauth-protected-resource/mcp", pr_metadata, methods=["GET"]),
            Route("/.well-known/oauth-protected-resource", pr_metadata, methods=["GET"]),
            Route("/.well-known/oauth-authorization-server", as_metadata, methods=["GET"]),
            # Interoperability alias only: the app is not an OpenID Provider (no jwks_uri, no ID tokens).
            Route("/.well-known/openid-configuration", as_metadata, methods=["GET"]),
            Route("/oauth/authorize", self.authorize_get, methods=["GET"]),
            Route("/oauth/authorize", self.authorize_post, methods=["POST"]),
            Route("/oauth/token", self.token, methods=["POST"]),
            Route("/oidc/login", self.oidc_login, methods=["GET"]),
            Route("/oidc/callback", self.oidc_callback, methods=["GET"]),
        ]

    # Authorization request validation --------------------------------------

    async def validate_request(self, q: dict[str, str]) -> CimdMetadata:
        """Validate an authorization request exactly the same way at every step."""
        if (
            q.get("response_type") != "code"
            or not q.get("client_id")
            or not q.get("redirect_uri")
            or not q.get("code_challenge")
            or q.get("code_challenge_method") != "S256"
            or not 43 <= len(q["code_challenge"]) <= 128
        ):
            raise ValueError("Invalid OAuth request")
        if q.get("resource") and q["resource"] != self.settings.resource:
            raise ValueError("Invalid resource")
        if not is_cimd_client_id(q["client_id"]):
            raise ValueError("Invalid client_id")
        metadata = await self.fetch_client_metadata(q["client_id"])
        if q["redirect_uri"] not in metadata.redirect_uris:
            raise ValueError("Invalid redirect_uri")
        return metadata

    async def _decode_and_validate(self, oauth: str | None) -> tuple[dict[str, str], CimdMetadata] | None:
        if not oauth:
            return None
        try:
            q = decode_oauth(oauth)
            return q, await self.validate_request(q)
        except Exception:  # noqa: BLE001 - every failure is an invalid request
            return None

    def _login_url(self, oauth: str) -> str:
        return self.settings.public_url + "/oidc/login?" + urlencode({"oauth": oauth})

    def _too_many(self) -> Response:
        return error_page("Too many sign-in attempts. Wait a minute and try again.", status=429)

    # /oauth/authorize ------------------------------------------------------

    async def authorize_get(self, request: Request) -> Response:
        if not self.rate_limiter.allow(_client_ip(request)):
            return self._too_many()
        q = {key: value for key, value in request.query_params.items()}
        try:
            await self.validate_request(q)
        except Exception:  # noqa: BLE001
            return invalid_request_page()
        # Sign-in is OIDC only: go straight to the identity provider.
        return RedirectResponse(self._login_url(encode_oauth(q)), status_code=302, headers={"Cache-Control": "no-store"})

    async def authorize_post(self, request: Request) -> Response:
        if not self.rate_limiter.allow(_client_ip(request)):
            return self._too_many()
        form = await request.form()
        oauth = form.get("oauth")
        oauth = oauth if isinstance(oauth, str) else None
        validated = await self._decode_and_validate(oauth)
        if validated is None or oauth is None:
            return invalid_request_page()
        q, _metadata = validated

        action = form.get("action")
        ticket = form.get("ticket")
        identity = (
            self.signer.verify_login_ticket(ticket, oauth, self.settings.oidc_issuer) if isinstance(ticket, str) and ticket else None
        )
        if action not in {"approve", "deny"} or identity is None:
            return error_page(
                "Your sign-in has expired or is not valid. Please sign in again.",
                status=401,
                retry_url=self._login_url(oauth),
                retry_label=self.settings.oidc_button_label,
            )

        common = {"iss": self.settings.public_url}
        if q.get("state"):
            common["state"] = q["state"]
        if action == "deny":
            AUDIT.record(principal=f"{identity.issuer}#{identity.subject}", repository=None, operation="oauth_consent_denied", success=True, duration_ms=0)
            return RedirectResponse(_with_query(q["redirect_uri"], {"error": "access_denied", **common}), status_code=302)

        code = random_token()
        self.store.save_authorization_code(
            code,
            AuthorizationCode(
                client_id=q["client_id"],
                redirect_uri=q["redirect_uri"],
                challenge=q["code_challenge"],
                identity=identity,
                scope=q.get("scope") or SCOPE,
            ),
            ttl=CODE_TTL,
        )
        AUDIT.record(principal=f"{identity.issuer}#{identity.subject}", repository=None, operation="oauth_consent_approved", success=True, duration_ms=0)
        return RedirectResponse(_with_query(q["redirect_uri"], {"code": code, **common}), status_code=302)

    # /oauth/token ----------------------------------------------------------

    async def token(self, request: Request) -> Response:
        headers = {"Cache-Control": "no-store", "Pragma": "no-cache"}  # RFC 6749 section 5.1

        def error(code: str, status: int = 400) -> Response:
            return JSONResponse({"error": code}, status_code=status, headers=headers)

        try:
            form = await request.form()
        except Exception:  # noqa: BLE001
            return error("invalid_request")
        b = {key: value for key, value in form.items() if isinstance(value, str)}
        if b.get("resource") and b["resource"] != self.settings.resource:
            return error("invalid_target")

        if b.get("grant_type") == "authorization_code":
            record = self.store.consume_authorization_code(b["code"]) if b.get("code") else None
            if (
                record is None
                or b.get("client_id") != record.client_id
                or b.get("redirect_uri") != record.redirect_uri
                or not b.get("code_verifier")
                or not verify_s256(b["code_verifier"], record.challenge)
                or record.identity.issuer != self.settings.oidc_issuer
            ):
                return error("invalid_grant")
            access = self.signer.issue_access_token(record.identity, record.client_id, record.scope)
            refresh = random_token()
            self.store.save_refresh_token(
                refresh, RefreshToken(client_id=record.client_id, identity=record.identity, scope=record.scope), ttl=REFRESH_TOKEN_TTL,
            )
            return JSONResponse(
                {"access_token": access, "token_type": "Bearer", "expires_in": 3600, "refresh_token": refresh, "scope": record.scope},
                headers=headers,
            )

        if b.get("grant_type") == "refresh_token":
            record = self.store.get_refresh_token(b["refresh_token"]) if b.get("refresh_token") else None
            # A token issued under another IdP (OIDC_ISSUER changed) keeps no access.
            if record is None or b.get("client_id") != record.client_id or record.identity.issuer != self.settings.oidc_issuer:
                return error("invalid_grant")
            access = self.signer.issue_access_token(record.identity, record.client_id, record.scope)
            return JSONResponse({"access_token": access, "token_type": "Bearer", "expires_in": 3600, "scope": record.scope}, headers=headers)

        return error("unsupported_grant_type")

    # /oidc/login and /oidc/callback -----------------------------------------

    def _set_cookie(self, response: Response, value: str, max_age: int) -> None:
        response.set_cookie(
            COOKIE_NAME, value, max_age=max_age, path=COOKIE_PATH, httponly=True,
            secure=self.settings.production, samesite="lax",
        )

    async def oidc_login(self, request: Request) -> Response:
        if not self.rate_limiter.allow(_client_ip(request)):
            return self._too_many()
        oauth = request.query_params.get("oauth")
        # This server has no web UI of its own: sign-in always belongs to an OAuth authorization request.
        if await self._decode_and_validate(oauth) is None or oauth is None:
            return invalid_request_page()

        state, nonce, verifier = random_token(), random_token(), random_token(48)
        try:
            url = await self.oidc.authorization_url(state=state, nonce=nonce, code_verifier=verifier)
        except OidcError as exc:
            LOGGER.warning("oidc login unavailable: %s", exc)
            return error_page(
                "Single sign-on is not available right now. Try again later.",
                status=502, retry_url=self._login_url(oauth), retry_label=self.settings.oidc_button_label,
            )
        self.store.save_oidc_state(state, OidcLoginState(verifier=verifier, nonce=nonce, purpose="oauth", oauth=oauth), ttl=STATE_TTL)
        response = RedirectResponse(url, status_code=302, headers={"Cache-Control": "no-store"})
        self._set_cookie(response, state, STATE_TTL)
        return response

    async def oidc_callback(self, request: Request) -> Response:
        started = time.perf_counter()
        if not self.rate_limiter.allow(_client_ip(request)):
            return self._too_many()

        def fail(reason: str, message: str, *, status: int = 400, oauth: str | None = None) -> Response:
            LOGGER.warning("oidc sign-in failed: %s", reason)
            AUDIT.record(
                principal="anonymous", repository=None, operation="oidc_sign_in", success=False,
                duration_ms=(time.perf_counter() - started) * 1000,
            )
            response = error_page(
                message, status=status,
                retry_url=self._login_url(oauth) if oauth else None,
                retry_label=self.settings.oidc_button_label,
            )
            response.delete_cookie(COOKIE_NAME, path=COOKIE_PATH, httponly=True, secure=self.settings.production, samesite="lax")
            return response

        state = request.query_params.get("state") or ""
        cookie_state = request.cookies.get(COOKIE_NAME) or ""

        # Login-CSRF protection: the browser that started the sign-in must be the one finishing it.
        if not state or not cookie_state or not hmac.compare_digest(state.encode(), cookie_state.encode()):
            return fail("state does not match the sign-in cookie", "This sign-in link is not valid for this browser. Start again.")
        pending = self.store.consume_oidc_state(state)
        if pending is None:
            return fail("unknown, expired or replayed state", "This sign-in has expired or was already used. Start again.")

        if request.query_params.get("error"):
            # The IdP's error code is a fixed vocabulary; its free-text description is not logged.
            reason = "".join(ch for ch in request.query_params["error"][:64] if ch.isalnum() or ch in "_-")
            return fail(f"IdP returned error={reason}", "The identity provider did not complete the sign-in.", oauth=pending.oauth)
        code = request.query_params.get("code")
        if not code:
            return fail("callback without code", "The identity provider did not complete the sign-in.", oauth=pending.oauth)

        validated = await self._decode_and_validate(pending.oauth)
        if validated is None or pending.oauth is None:
            return fail("authorization request no longer valid", "The authorization request is no longer valid. Start again from your MCP client.")
        q, metadata = validated

        try:
            identity, _claims = await self.oidc.complete(code=code, code_verifier=pending.verifier, nonce=pending.nonce)
        except OidcError as exc:
            return fail(str(exc), "Signing in with the identity provider failed.", oauth=pending.oauth)

        LOGGER.info("oidc sign-in succeeded for subject %s", identity.subject)
        AUDIT.record(
            principal=f"{identity.issuer}#{identity.subject}", repository=None, operation="oidc_sign_in", success=True,
            duration_ms=(time.perf_counter() - started) * 1000,
        )
        ticket = self.signer.issue_login_ticket(identity, pending.oauth)
        response = consent_page(
            oauth=pending.oauth, ticket=ticket, user_name=identity.name,
            client_name=metadata.client_name or q["client_id"], client_id=q["client_id"], redirect_uri=q["redirect_uri"],
        )
        response.delete_cookie(COOKIE_NAME, path=COOKIE_PATH, httponly=True, secure=self.settings.production, samesite="lax")
        return response
