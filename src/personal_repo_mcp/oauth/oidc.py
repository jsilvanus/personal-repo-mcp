"""OIDC relying party toward the configured identity provider (e.g. authentik).

The app never issues ID tokens and never acts as an OpenID Provider: it sends the
browser to the IdP, redeems the code at the IdP's token endpoint (PKCE + state +
nonce) and verifies the returned ID token against the IdP's JWKS.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx2
from authlib.integrations.httpx_client import AsyncOAuth2Client
from authlib.oidc.core import CodeIDToken
from joserfc import jwt
from joserfc.jwk import KeySet

from ..config import OAuthSettings
from .store import Identity

# Asymmetric algorithms only: the ID token must be verifiable with the IdP's public JWKS
# (authentik: set a signing key on the provider so tokens are RS256).
_ASYMMETRIC_ALGORITHMS = (
    "RS256", "RS384", "RS512", "PS256", "PS384", "PS512", "ES256", "ES384", "ES512", "EdDSA",
)
_TIMEOUT = 10.0
_LEEWAY = 120


class OidcError(Exception):
    """A sign-in failure. The message is safe to log; it never contains tokens."""


class OidcClient:
    def __init__(self, settings: OAuthSettings, *, transport: httpx2.AsyncBaseTransport | None = None) -> None:
        self.settings = settings
        self._transport = transport
        self._metadata: dict[str, Any] | None = None
        self._jwks: KeySet | None = None
        self._lock = asyncio.Lock()

    def _http(self) -> httpx2.AsyncClient:
        kwargs: dict[str, Any] = {"timeout": _TIMEOUT}
        if self._transport is not None:
            kwargs["transport"] = self._transport
        return httpx2.AsyncClient(**kwargs)

    def _oauth_client(self) -> AsyncOAuth2Client:
        s = self.settings
        kwargs: dict[str, Any] = {"timeout": _TIMEOUT}
        if self._transport is not None:
            kwargs["transport"] = self._transport
        return AsyncOAuth2Client(
            client_id=s.oidc_client_id,
            client_secret=s.oidc_client_secret,
            token_endpoint_auth_method="client_secret_basic" if s.oidc_client_secret else "none",
            scope=s.oidc_scopes,
            redirect_uri=s.redirect_uri,
            code_challenge_method="S256",
            **kwargs,
        )

    async def metadata(self) -> dict[str, Any]:
        """Discovery on first use, cached; a failure is not cached, so a later request retries."""
        if self._metadata is not None:
            return self._metadata
        async with self._lock:
            if self._metadata is not None:
                return self._metadata
            issuer = self.settings.oidc_issuer
            url = issuer.rstrip("/") + "/.well-known/openid-configuration"
            try:
                async with self._http() as client:
                    response = await client.get(url, headers={"accept": "application/json"})
                response.raise_for_status()
                document = response.json()
            except (httpx2.HTTPError, ValueError) as exc:
                raise OidcError(f"OIDC discovery failed: {type(exc).__name__}") from exc
            if not isinstance(document, dict) or document.get("issuer") != issuer:
                raise OidcError("OIDC discovery document issuer does not match OIDC_ISSUER")
            for key in ("authorization_endpoint", "token_endpoint", "jwks_uri"):
                if not isinstance(document.get(key), str):
                    raise OidcError(f"OIDC discovery document lacks {key}")
            self._metadata = document
            return document

    async def _key_set(self, *, force: bool = False) -> KeySet:
        if self._jwks is not None and not force:
            return self._jwks
        metadata = await self.metadata()
        try:
            async with self._http() as client:
                response = await client.get(metadata["jwks_uri"], headers={"accept": "application/json"})
            response.raise_for_status()
            self._jwks = KeySet.import_key_set(response.json())
        except Exception as exc:  # noqa: BLE001 - any JWKS failure is a sign-in failure
            raise OidcError(f"Cannot load the IdP JWKS: {type(exc).__name__}") from exc
        return self._jwks

    async def authorization_url(self, *, state: str, nonce: str, code_verifier: str) -> str:
        metadata = await self.metadata()
        async with self._oauth_client() as client:
            url, _ = client.create_authorization_url(
                metadata["authorization_endpoint"], state=state, code_verifier=code_verifier, nonce=nonce,
            )
        return url

    async def complete(self, *, code: str, code_verifier: str, nonce: str) -> tuple[Identity, dict[str, Any]]:
        """Redeem the code (PKCE) and return the verified identity and its claims."""
        metadata = await self.metadata()
        try:
            async with self._oauth_client() as client:
                token = await client.fetch_token(
                    metadata["token_endpoint"],
                    grant_type="authorization_code",
                    code=code,
                    code_verifier=code_verifier,
                )
        except Exception as exc:  # noqa: BLE001 - authlib raises several error types
            raise OidcError(f"OIDC code exchange failed: {type(exc).__name__}") from exc

        id_token = token.get("id_token")
        if not isinstance(id_token, str):
            raise OidcError("The IdP did not return an ID token")
        claims = await self._verify_id_token(id_token, nonce=nonce, access_token=token.get("access_token"))

        if not claims.get("email") and isinstance(token.get("access_token"), str):
            claims = await self._merge_userinfo(claims, token["access_token"], metadata)

        subject = claims["sub"]
        name = claims.get("name") or claims.get("preferred_username") or claims.get("email") or subject
        return Identity(issuer=self.settings.oidc_issuer, subject=str(subject), name=str(name)), claims

    async def _verify_id_token(self, id_token: str, *, nonce: str, access_token: Any) -> dict[str, Any]:
        metadata = await self.metadata()
        advertised = metadata.get("id_token_signing_alg_values_supported") or ["RS256"]
        algorithms = [alg for alg in advertised if alg in _ASYMMETRIC_ALGORITHMS] or ["RS256"]
        try:
            try:
                decoded = jwt.decode(id_token, await self._key_set(), algorithms=algorithms)
            except OidcError:
                raise
            except Exception:  # noqa: BLE001 - unknown kid after key rotation: refetch once
                decoded = jwt.decode(id_token, await self._key_set(force=True), algorithms=algorithms)
            claims = CodeIDToken(
                decoded.claims,
                decoded.header,
                options={
                    "iss": {"essential": True, "value": self.settings.oidc_issuer},
                    "aud": {"essential": True, "value": self.settings.oidc_client_id},
                    "sub": {"essential": True},
                    "exp": {"essential": True},
                },
                params={
                    "nonce": nonce,
                    "client_id": self.settings.oidc_client_id,
                    **({"access_token": access_token} if isinstance(access_token, str) else {}),
                },
            )
            claims.validate(leeway=_LEEWAY)
        except OidcError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise OidcError(f"ID token rejected: {type(exc).__name__}") from exc
        if claims.get("nonce") != nonce:
            raise OidcError("ID token rejected: nonce mismatch")
        return dict(claims)

    async def _merge_userinfo(self, claims: dict[str, Any], access_token: str, metadata: dict[str, Any]) -> dict[str, Any]:
        endpoint = metadata.get("userinfo_endpoint")
        if not isinstance(endpoint, str):
            return claims
        try:
            async with self._http() as client:
                response = await client.get(endpoint, headers={"authorization": f"Bearer {access_token}"})
            response.raise_for_status()
            info = response.json()
        except Exception:  # noqa: BLE001 - userinfo only adds display data
            return claims
        if not isinstance(info, dict) or info.get("sub") != claims.get("sub"):
            return claims
        merged = dict(claims)
        for key in ("email", "email_verified", "name", "preferred_username"):
            if key in info and key not in merged:
                merged[key] = info[key]
        return merged
