from __future__ import annotations

import base64
from pathlib import Path

import pytest

from personal_repo_mcp.config import ConfigurationError, load_oauth_settings

SECRET = base64.b64encode(b"k" * 32).decode()
OIDC_VARS = (
    "OIDC_ISSUER", "OIDC_CLIENT_ID", "OIDC_CLIENT_SECRET", "OIDC_CLIENT_SECRET_FILE", "OIDC_SCOPES",
    "OIDC_BUTTON_LABEL", "JWT_SECRET", "JWT_SECRET_FILE", "PERSONAL_REPO_MCP_PUBLIC_URL", "PERSONAL_REPO_MCP_OAUTH_DB",
)


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch):
    for name in OIDC_VARS:
        monkeypatch.delenv(name, raising=False)

    def apply(**values: str) -> None:
        defaults = {
            "OIDC_ISSUER": "https://auth.example.org/application/o/repo/",
            "OIDC_CLIENT_ID": "repo",
            "JWT_SECRET": SECRET,
            "PERSONAL_REPO_MCP_PUBLIC_URL": "https://mcp.example.org/",
        }
        defaults.update(values)
        for name, value in defaults.items():
            monkeypatch.setenv(name, value)

    return apply


def test_unset_or_empty_issuer_disables_oauth(env, monkeypatch, tmp_path: Path) -> None:
    assert load_oauth_settings(tmp_path / "repositories") is None
    monkeypatch.setenv("OIDC_ISSUER", "  ")
    assert load_oauth_settings(tmp_path / "repositories") is None


def test_valid_configuration(env, tmp_path: Path) -> None:
    env()
    settings = load_oauth_settings(tmp_path / "repositories")
    assert settings is not None
    assert settings.public_url == "https://mcp.example.org"
    assert settings.resource == "https://mcp.example.org/mcp"
    assert settings.redirect_uri == "https://mcp.example.org/oidc/callback"
    assert settings.oidc_issuer == "https://auth.example.org/application/o/repo/"  # trailing slash kept
    assert settings.oidc_scopes == "openid email profile"
    assert settings.oidc_button_label == "Sign in with single sign-on"
    assert settings.oidc_client_secret is None
    assert settings.production is True
    assert settings.jwt_secret == b"k" * 32
    assert settings.database_path == (tmp_path / "data" / "oauth.sqlite").resolve()


def test_secret_files_and_overrides(env, tmp_path: Path) -> None:
    secret_file = tmp_path / "client_secret"
    secret_file.write_text("from-file\n")
    jwt_file = tmp_path / "jwt"
    jwt_file.write_text(SECRET + "\n")
    env(
        OIDC_CLIENT_SECRET_FILE=str(secret_file),
        JWT_SECRET_FILE=str(jwt_file),
        JWT_SECRET="",
        OIDC_SCOPES="openid  email",
        OIDC_BUTTON_LABEL="Use SSO",
        PERSONAL_REPO_MCP_OAUTH_DB=str(tmp_path / "x.sqlite"),
        PERSONAL_REPO_MCP_PUBLIC_URL="http://localhost:8000",
        OIDC_ISSUER="http://localhost:9000/",
    )
    settings = load_oauth_settings(tmp_path)
    assert settings is not None
    assert settings.oidc_client_secret == "from-file"
    assert settings.oidc_scopes == "openid email"
    assert settings.oidc_button_label == "Use SSO"
    assert settings.database_path == (tmp_path / "x.sqlite").resolve()
    assert settings.production is False


@pytest.mark.parametrize(
    ("values", "message"),
    [
        ({"OIDC_CLIENT_ID": ""}, "OIDC_CLIENT_ID"),
        ({"PERSONAL_REPO_MCP_PUBLIC_URL": ""}, "PERSONAL_REPO_MCP_PUBLIC_URL"),
        ({"PERSONAL_REPO_MCP_PUBLIC_URL": "mcp.example.org"}, "PERSONAL_REPO_MCP_PUBLIC_URL"),
        ({"OIDC_ISSUER": "not a url"}, "OIDC_ISSUER"),
        ({"OIDC_ISSUER": "http://auth.example.org/"}, "https"),
        ({"OIDC_SCOPES": "email profile"}, "openid"),
        ({"JWT_SECRET": ""}, "JWT_SECRET"),
        ({"JWT_SECRET": base64.b64encode(b"short").decode()}, "32 bytes"),
        ({"JWT_SECRET": "not base64!!"}, "base64"),
    ],
)
def test_configuration_errors(env, tmp_path: Path, values: dict[str, str], message: str) -> None:
    env(**values)
    with pytest.raises(ConfigurationError, match=message):
        load_oauth_settings(tmp_path)
