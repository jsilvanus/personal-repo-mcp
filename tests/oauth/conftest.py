from __future__ import annotations

import base64
import hashlib
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx
import httpx2
import pytest

from personal_repo_mcp.config import OAuthSettings, Settings
from personal_repo_mcp.main import create_app
from personal_repo_mcp.oauth.cimd import CimdMetadata

from .fake_idp import ISSUER, FakeIdp

PUBLIC_URL = "http://testserver"
CLIENT_ID = "https://client.example/oauth/client.json"
REDIRECT_URI = "https://client.example/callback"
STATIC_TOKEN = "static-token"
JWT_SECRET = b"s" * 32


def base_settings(tmp_path: Path, oauth: OAuthSettings | None) -> Settings:
    return Settings(
        host="127.0.0.1",
        port=8000,
        token=STATIC_TOKEN,
        github_pat="github-pat",
        git_backend="git",
        allowed_hosts=("testserver",),
        allowed_origins=("http://testserver",),
        repository_root=tmp_path / "repositories",
        repositories=(),
        repository_patterns=(),
        oauth=oauth,
    )


def oauth_settings(tmp_path: Path, **overrides) -> OAuthSettings:
    values = dict(
        public_url=PUBLIC_URL,
        jwt_secret=JWT_SECRET,
        oidc_issuer=ISSUER,
        oidc_client_id="repo-client",
        oidc_client_secret="idp-secret",
        oidc_scopes="openid email profile",
        oidc_button_label="Sign in with single sign-on",
        database_path=tmp_path / "data" / "oauth.sqlite",
        production=False,
    )
    values.update(overrides)
    return OAuthSettings(**values)


async def fetch_client_metadata(client_id: str) -> CimdMetadata:
    if client_id != CLIENT_ID:
        raise ValueError("unknown client")
    return CimdMetadata(client_id=CLIENT_ID, client_name="Test Client", redirect_uris=(REDIRECT_URI,))


def pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


def query_of(url: str) -> dict[str, str]:
    return {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}


class Harness:
    def __init__(self, app, idp: FakeIdp, client: httpx.AsyncClient, idp_client: httpx.AsyncClient) -> None:
        self.app, self.idp, self.client, self.idp_client = app, idp, client, idp_client
        self.verifier, self.challenge = pkce_pair()

    def authorize_params(self, **overrides) -> dict[str, str]:
        params = {
            "response_type": "code",
            "client_id": CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
            "code_challenge": self.challenge,
            "code_challenge_method": "S256",
            "state": "client-state",
            "scope": "mcp",
            "resource": PUBLIC_URL + "/mcp",
        }
        params.update(overrides)
        return params

    async def start(self) -> tuple[str, str]:
        """authorize -> /oidc/login -> IdP; returns (IdP authorize URL, oauth payload)."""
        r = await self.client.get("/oauth/authorize", params=self.authorize_params())
        assert r.status_code == 302, r.text
        login = r.headers["location"]
        assert login.startswith(PUBLIC_URL + "/oidc/login?oauth=")
        oauth = query_of(login)["oauth"]
        r = await self.client.get(login)
        assert r.status_code == 302, r.text
        assert r.headers["location"].startswith("http://idp.test/")
        return r.headers["location"], oauth

    async def idp_redirect(self, idp_url: str) -> str:
        r = await self.idp_client.get(idp_url)
        assert r.status_code == 302
        return r.headers["location"]

    async def consent(self) -> tuple[httpx.Response, str]:
        idp_url, oauth = await self.start()
        callback = await self.idp_redirect(idp_url)
        r = await self.client.get(callback)
        return r, oauth

    @staticmethod
    def ticket_of(page: str) -> str:
        marker = 'name="ticket" value="'
        start = page.index(marker) + len(marker)
        return page[start:page.index('"', start)]

    async def approve(self) -> dict[str, str]:
        r, oauth = await self.consent()
        assert r.status_code == 200, r.text
        r = await self.client.post("/oauth/authorize", data={"oauth": oauth, "ticket": self.ticket_of(r.text), "action": "approve"})
        assert r.status_code == 302, r.text
        return query_of(r.headers["location"])

    async def tokens(self) -> dict:
        redirect = await self.approve()
        r = await self.client.post("/oauth/token", data={
            "grant_type": "authorization_code",
            "code": redirect["code"],
            "client_id": CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
            "code_verifier": self.verifier,
            "resource": PUBLIC_URL + "/mcp",
        })
        assert r.status_code == 200, r.text
        return r.json()


async def mcp_tools_list(client: httpx.AsyncClient, token: str | None) -> httpx.Response:
    headers = {"accept": "application/json, text/event-stream", "content-type": "application/json"}
    if token:
        headers["authorization"] = f"Bearer {token}"
    return await client.post("/mcp/", headers=headers, json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})


@asynccontextmanager
async def running(settings: Settings, idp: FakeIdp):
    app = create_app(
        settings,
        oauth_options={
            "oidc_transport": httpx2.ASGITransport(app=idp.app()),
            "fetch_client_metadata": fetch_client_metadata,
        },
    )
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=PUBLIC_URL) as client:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=idp.app()), base_url="http://idp.test") as idp_client:
                yield Harness(app, idp, client, idp_client)


@pytest.fixture
def idp() -> FakeIdp:
    return FakeIdp()


@pytest.fixture
def make_harness(tmp_path: Path, idp: FakeIdp):
    def factory(**overrides):
        return running(base_settings(tmp_path, oauth_settings(tmp_path, **overrides)), idp)

    return factory


