"""The app's own tokens: HS256 JWT access tokens and consent-step login tickets."""

from __future__ import annotations

import base64
import hashlib
import secrets
import time
from typing import Any

from joserfc import jwt
from joserfc.errors import JoseError
from joserfc.jwk import OctKey
from joserfc.jwt import JWTClaimsRegistry

from .store import Identity

ACCESS_TOKEN_TTL = 3600
LOGIN_TICKET_TTL = 600
_ALGORITHMS = ["HS256"]


def random_token(size: int = 32) -> str:
    return secrets.token_urlsafe(size)


def sha256_b64url(value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def verify_s256(verifier: str, challenge: str) -> bool:
    return secrets.compare_digest(sha256_b64url(verifier), challenge)


class TokenSigner:
    def __init__(self, secret: bytes, issuer: str, resource: str) -> None:
        self._key = OctKey.import_key(secret)
        self.issuer = issuer
        self.resource = resource
        self.ticket_audience = issuer + "/oauth/authorize"

    def _encode(self, claims: dict[str, Any]) -> str:
        return jwt.encode({"alg": "HS256", "typ": "JWT"}, claims, self._key, algorithms=_ALGORITHMS)

    def _decode(self, token: str, audience: str) -> dict[str, Any] | None:
        try:
            decoded = jwt.decode(token, self._key, algorithms=_ALGORITHMS)
            JWTClaimsRegistry(
                iss={"essential": True, "value": self.issuer},
                aud={"essential": True, "value": audience},
                sub={"essential": True},
                exp={"essential": True},
            ).validate(decoded.claims)
        except (JoseError, ValueError):
            return None
        return dict(decoded.claims)

    def issue_access_token(self, identity: Identity, client_id: str, scope: str) -> str:
        now = int(time.time())
        return self._encode({
            "iss": self.issuer,
            "aud": self.resource,
            "sub": identity.subject,
            "idp": identity.issuer,
            "client_id": client_id,
            "scope": scope,
            "iat": now,
            "exp": now + ACCESS_TOKEN_TTL,
        })

    def verify_access_token(self, token: str) -> dict[str, Any] | None:
        claims = self._decode(token, self.resource)
        if claims is None or claims.get("typ") == "login":
            return None
        return claims

    def issue_login_ticket(self, identity: Identity, oauth: str) -> str:
        """Signed proof, bound to one authorization request, that the user signed in via OIDC."""
        now = int(time.time())
        return self._encode({
            "typ": "login",
            "iss": self.issuer,
            "aud": self.ticket_audience,
            "sub": identity.subject,
            "idp": identity.issuer,
            "name": identity.name,
            "oauth": sha256_b64url(oauth),
            "iat": now,
            "exp": now + LOGIN_TICKET_TTL,
        })

    def verify_login_ticket(self, ticket: str, oauth: str, expected_idp: str) -> Identity | None:
        claims = self._decode(ticket, self.ticket_audience)
        if (
            claims is None
            or claims.get("typ") != "login"
            or claims.get("oauth") != sha256_b64url(oauth)
            or claims.get("idp") != expected_idp
            or not isinstance(claims.get("sub"), str)
        ):
            return None
        return Identity(issuer=claims["idp"], subject=claims["sub"], name=str(claims.get("name") or claims["sub"]))
