from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from personal_repo_mcp.main import create_app
from personal_repo_mcp.oauth.server import COOKIE_NAME, RateLimiter

from .conftest import (
    CLIENT_ID,
    PUBLIC_URL,
    REDIRECT_URI,
    STATIC_TOKEN,
    base_settings,
    mcp_tools_list,
    query_of,
)


# OIDC off ------------------------------------------------------------------


async def test_oidc_off_keeps_todays_behaviour(tmp_path: Path) -> None:
    app = create_app(base_settings(tmp_path, None))
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=PUBLIC_URL) as client:
            r = await mcp_tools_list(client, None)
            assert r.status_code == 401
            assert r.headers["www-authenticate"] == "Bearer"
            assert (await client.get("/oidc/login")).status_code == 401
            auth = {"authorization": f"Bearer {STATIC_TOKEN}"}
            for path in ("/oidc/login", "/oidc/callback", "/oauth/authorize", "/.well-known/oauth-protected-resource/mcp",
                         "/.well-known/oauth-authorization-server", "/.well-known/openid-configuration"):
                assert (await client.get(path, headers=auth)).status_code == 404, path
            r = await mcp_tools_list(client, STATIC_TOKEN)
            assert r.status_code == 200
            assert "tools" in r.json()["result"]


# Metadata and the resource server ------------------------------------------------


async def test_metadata_endpoints(make_harness) -> None:
    async with make_harness() as h:
        for path in ("/.well-known/oauth-protected-resource/mcp", "/.well-known/oauth-protected-resource"):
            body = (await h.client.get(path)).json()
            assert body["resource"] == PUBLIC_URL + "/mcp"
            assert body["authorization_servers"] == [PUBLIC_URL]
        for path in ("/.well-known/oauth-authorization-server", "/.well-known/openid-configuration"):
            body = (await h.client.get(path)).json()
            assert body["issuer"] == PUBLIC_URL
            assert body["token_endpoint_auth_methods_supported"] == ["none"]
            assert body["code_challenge_methods_supported"] == ["S256"]
            assert body["client_id_metadata_document_supported"] is True
            # The app is not an OpenID Provider.
            for key in ("jwks_uri", "id_token_signing_alg_values_supported", "userinfo_endpoint"):
                assert key not in body


async def test_mcp_challenge_and_static_token(make_harness) -> None:
    async with make_harness() as h:
        r = await mcp_tools_list(h.client, None)
        assert r.status_code == 401
        challenge = r.headers["www-authenticate"]
        assert challenge.startswith(f'Bearer resource_metadata="{PUBLIC_URL}/.well-known/oauth-protected-resource/mcp"')
        assert "error=" not in challenge

        r = await mcp_tools_list(h.client, "not-a-valid-token")
        assert r.status_code == 401
        assert 'error="invalid_token"' in r.headers["www-authenticate"]

        # Existing deployments keep working with the static bearer token.
        r = await mcp_tools_list(h.client, STATIC_TOKEN)
        assert r.status_code == 200
        assert (await h.client.get("/healthz")).status_code == 200


# Full MCP OAuth flow via OIDC ------------------------------------------------------


async def test_full_flow_confidential_client(make_harness, idp) -> None:
    async with make_harness() as h:
        r, _oauth = await h.consent()
        assert r.status_code == 200
        assert "Test User" in r.text and "Test Client" in r.text
        csp = r.headers["content-security-policy"]
        assert "form-action 'self' https://client.example" in csp
        assert r.headers["cache-control"] == "no-store"
        # The sign-in cookie is cleared after the callback.
        assert COOKIE_NAME in r.headers.get("set-cookie", "") and "Max-Age=0" in r.headers["set-cookie"]

        # IdP saw PKCE, nonce and the registered redirect URI.
        sent = idp.authorize_requests[-1]
        assert sent["redirect_uri"] == PUBLIC_URL + "/oidc/callback"
        assert sent["nonce"] and sent["code_challenge"]
        assert idp.token_requests[-1]["code_verifier"]

    async with make_harness() as h:
        tokens = await h.tokens()
        assert tokens["token_type"] == "Bearer" and tokens["refresh_token"]
        r = await mcp_tools_list(h.client, tokens["access_token"])
        assert r.status_code == 200, r.text
        assert any(tool["name"] == "get_repositories" for tool in r.json()["result"]["tools"])

        refreshed = await h.client.post("/oauth/token", data={
            "grant_type": "refresh_token", "refresh_token": tokens["refresh_token"], "client_id": CLIENT_ID,
        })
        assert refreshed.status_code == 200
        assert refreshed.headers["cache-control"] == "no-store"
        assert (await mcp_tools_list(h.client, refreshed.json()["access_token"])).status_code == 200

        wrong_client = await h.client.post("/oauth/token", data={
            "grant_type": "refresh_token", "refresh_token": tokens["refresh_token"], "client_id": "https://other.example/c.json",
        })
        assert wrong_client.json() == {"error": "invalid_grant"}


async def test_public_oidc_client_and_userinfo(make_harness, idp) -> None:
    idp.client_secret = None
    idp.claims = {}  # no name/email in the ID token: userinfo supplies the email
    async with make_harness(oidc_client_secret=None) as h:
        r, _ = await h.consent()
        assert r.status_code == 200, r.text
        assert "tester@example.org" in r.text
        assert idp.token_requests[-1]["client_id"] == "repo-client"


async def test_redirect_carries_state_and_iss(make_harness) -> None:
    async with make_harness() as h:
        redirect = await h.approve()
        assert redirect["state"] == "client-state"
        assert redirect["iss"] == PUBLIC_URL


async def test_deny_redirects_with_access_denied(make_harness) -> None:
    async with make_harness() as h:
        r, oauth = await h.consent()
        r = await h.client.post("/oauth/authorize", data={"oauth": oauth, "ticket": h.ticket_of(r.text), "action": "deny"})
        assert r.status_code == 302
        q = query_of(r.headers["location"])
        assert r.headers["location"].startswith(REDIRECT_URI)
        assert q["error"] == "access_denied" and q["state"] == "client-state"


# Rejections -------------------------------------------------------------------------


async def test_state_cookie_mismatch_refused(make_harness) -> None:
    async with make_harness() as h:
        idp_url, _ = await h.start()
        callback = await h.idp_redirect(idp_url)
        h.client.cookies.clear()
        r = await h.client.get(callback, headers={"cookie": f"{COOKIE_NAME}=some-other-state"})
        assert r.status_code == 400
        assert "not valid for this browser" in r.text

    async with make_harness() as h:
        idp_url, _ = await h.start()
        callback = await h.idp_redirect(idp_url)
        h.client.cookies.clear()
        r = await h.client.get(callback)
        assert r.status_code == 400


async def test_replayed_state_refused(make_harness) -> None:
    async with make_harness() as h:
        idp_url, _ = await h.start()
        callback = await h.idp_redirect(idp_url)
        state = query_of(callback)["state"]
        assert (await h.client.get(callback)).status_code == 200
        r = await h.client.get(callback, headers={"cookie": f"{COOKIE_NAME}={state}"})
        assert r.status_code == 400
        assert "already used" in r.text


async def test_wrong_nonce_or_audience_refused(make_harness, idp) -> None:
    idp.nonce_override = "attacker-nonce"
    async with make_harness() as h:
        r, _ = await h.consent()
        assert r.status_code == 400
        assert "Signing in with the identity provider failed." in r.text
    idp.nonce_override = None
    idp.audience_override = "another-client"
    async with make_harness() as h:
        r, _ = await h.consent()
        assert r.status_code == 400


async def test_idp_error_shows_error_page(make_harness, idp) -> None:
    idp.authorize_error = "access_denied"
    async with make_harness() as h:
        r, _ = await h.consent()
        assert r.status_code == 400
        assert "did not complete the sign-in" in r.text
        assert "/oidc/login?oauth=" in r.text  # a way back


async def test_consent_requires_valid_ticket(make_harness) -> None:
    async with make_harness() as h:
        r, oauth = await h.consent()
        ticket = h.ticket_of(r.text)
        for data in (
            {"oauth": oauth, "action": "approve"},
            {"oauth": oauth, "action": "approve", "ticket": ticket[:-3] + "abc"},
        ):
            r = await h.client.post("/oauth/authorize", data=data)
            assert r.status_code == 401

        # A ticket is bound to its own authorization request.
        other = h.authorize_params(state="another-state")
        from personal_repo_mcp.oauth.server import encode_oauth

        r = await h.client.post("/oauth/authorize", data={"oauth": encode_oauth(other), "ticket": ticket, "action": "approve"})
        assert r.status_code == 401

        # A login ticket is never an access token.
        assert (await mcp_tools_list(h.client, ticket)).status_code == 401


async def test_token_endpoint_rejections(make_harness) -> None:
    async with make_harness() as h:
        redirect = await h.approve()
        bad = await h.client.post("/oauth/token", data={
            "grant_type": "authorization_code", "code": redirect["code"], "client_id": CLIENT_ID,
            "redirect_uri": REDIRECT_URI, "code_verifier": "wrong-verifier-" + "x" * 40,
        })
        assert bad.json() == {"error": "invalid_grant"}
        # The code was consumed by the failed attempt: single use.
        replay = await h.client.post("/oauth/token", data={
            "grant_type": "authorization_code", "code": redirect["code"], "client_id": CLIENT_ID,
            "redirect_uri": REDIRECT_URI, "code_verifier": h.verifier,
        })
        assert replay.json() == {"error": "invalid_grant"}
        assert (await h.client.post("/oauth/token", data={"grant_type": "password"})).json() == {"error": "unsupported_grant_type"}
        wrong_resource = await h.client.post("/oauth/token", data={"grant_type": "refresh_token", "resource": "https://evil.example/mcp"})
        assert wrong_resource.json() == {"error": "invalid_target"}


async def test_invalid_authorization_requests(make_harness) -> None:
    async with make_harness() as h:
        for overrides in (
            {"redirect_uri": "https://evil.example/cb"},
            {"code_challenge_method": "plain"},
            {"client_id": "http://client.example/oauth/client.json"},
            {"resource": "https://evil.example/mcp"},
        ):
            r = await h.client.get("/oauth/authorize", params=h.authorize_params(**overrides))
            assert r.status_code == 400, overrides
        assert (await h.client.get("/oidc/login")).status_code == 400
        assert (await h.client.get("/oidc/login", params={"oauth": "garbage"})).status_code == 400


async def test_discovery_failure_is_retried(make_harness, idp) -> None:
    idp.discovery_down = True
    async with make_harness() as h:
        r = await h.client.get("/oauth/authorize", params=h.authorize_params())
        r = await h.client.get(r.headers["location"])
        assert r.status_code == 502
        idp.discovery_down = False
        r = await h.client.get("/oauth/authorize", params=h.authorize_params())
        r = await h.client.get(r.headers["location"])
        assert r.status_code == 302 and r.headers["location"].startswith("http://idp.test/")


async def test_tokens_from_another_issuer_are_refused(make_harness, tmp_path) -> None:
    async with make_harness() as h:
        tokens = await h.tokens()
    # Same database and secret, OIDC_ISSUER changed: refresh tokens no longer work.
    async with make_harness(oidc_issuer="http://other-idp.test/") as h:
        r = await h.client.post("/oauth/token", data={
            "grant_type": "refresh_token", "refresh_token": tokens["refresh_token"], "client_id": CLIENT_ID,
        })
        assert r.json() == {"error": "invalid_grant"}


def test_rate_limiter() -> None:
    limiter = RateLimiter(limit=2, window=60)
    assert limiter.allow("a") and limiter.allow("a")
    assert not limiter.allow("a")
    assert limiter.allow("b")


@pytest.mark.parametrize("path", ["/oauth/token"])
async def test_token_endpoint_is_public(make_harness, path) -> None:
    async with make_harness() as h:
        r = await h.client.post(path, data={})
        assert r.status_code == 400
