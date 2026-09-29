from __future__ import annotations

import base64
import binascii
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import parse as urlparse


class ConfigurationError(ValueError):
    """Raised when server configuration is invalid."""


@dataclass(frozen=True, slots=True)
class RepositoryConfig:
    """Configuration for one concrete repository workspace."""

    id: str
    name: str
    remote: str
    workspace: Path


@dataclass(frozen=True, slots=True)
class OAuthSettings:
    """OAuth authorization server + OIDC sign-in, enabled only when OIDC_ISSUER is set."""

    public_url: str
    jwt_secret: bytes
    oidc_issuer: str
    oidc_client_id: str
    oidc_client_secret: str | None
    oidc_scopes: str
    oidc_button_label: str
    database_path: Path
    production: bool

    @property
    def resource(self) -> str:
        return self.public_url + "/mcp"

    @property
    def redirect_uri(self) -> str:
        return self.public_url + "/oidc/callback"


@dataclass(frozen=True, slots=True)
class Settings:
    """Application configuration loaded from environment variables and JSON."""

    host: str
    port: int
    token: str
    github_pat: str
    git_backend: str
    allowed_hosts: tuple[str, ...]
    allowed_origins: tuple[str, ...]
    repository_root: Path
    repositories: tuple[RepositoryConfig, ...]
    repository_patterns: tuple[str, ...]
    oauth: OAuthSettings | None = None


def _csv(value: str, default: tuple[str, ...]) -> tuple[str, ...]:
    items = tuple(item.strip() for item in value.split(",") if item.strip())
    return items or default


def _read_secret(name: str, file_name: str, *, required: bool = True) -> str | None:
    """Read a secret from a file, falling back to the environment for compatibility."""
    path_value = os.getenv(file_name)
    if path_value:
        try:
            value = Path(path_value).read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise ConfigurationError(f"Cannot read secret file for {name}") from exc
        if value:
            return value
        if required:
            raise ConfigurationError(f"Secret file for {name} is empty")
        return None

    value = os.getenv(name)
    if value:
        return value
    if required:
        raise ConfigurationError(f"{name} or {file_name} must be set")
    return None


def _repository_config(raw: Any, root: Path) -> RepositoryConfig:
    if not isinstance(raw, dict):
        raise ConfigurationError("Each concrete repository must be an object")
    repo_id = str(raw.get("id", "")).strip()
    name = str(raw.get("name", repo_id)).strip()
    remote = str(raw.get("remote", "")).strip()
    workspace_value = str(raw.get("workspace", "")).strip()
    if not repo_id or not name or not remote or not workspace_value:
        raise ConfigurationError("Repository requires id, name, remote and workspace")
    if repo_id in {".", ".."} or "\\" in repo_id or any(part in {"", ".", ".."} for part in repo_id.split("/")):
        raise ConfigurationError(f"Invalid repository id: {repo_id!r}")
    workspace = Path(workspace_value)
    if not workspace.is_absolute():
        workspace = root / workspace
    workspace = workspace.resolve()
    if workspace == root or root not in workspace.parents:
        raise ConfigurationError(f"Repository workspace must be below repository root: {workspace}")
    return RepositoryConfig(id=repo_id, name=name, remote=remote, workspace=workspace)


def _load_repository_config(config_path: Path, inline: str) -> list[Any]:
    if config_path.exists():
        try:
            raw = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ConfigurationError(f"Cannot read repository configuration: {config_path}") from exc
    else:
        try:
            raw = json.loads(inline)
        except json.JSONDecodeError as exc:
            raise ConfigurationError("PERSONAL_REPO_MCP_REPOSITORIES is not valid JSON") from exc
    if isinstance(raw, dict):
        version = raw.get("version", 1)
        if version != 1:
            raise ConfigurationError(f"Unsupported repository configuration version: {version}")
        raw = raw.get("repositories")
    if not isinstance(raw, list):
        raise ConfigurationError("Repository configuration must contain a repositories array")
    return raw


def _parse_entries(raw: list[Any], root: Path) -> tuple[list[RepositoryConfig], list[str]]:
    repositories: list[RepositoryConfig] = []
    patterns: list[str] = []
    for item in raw:
        if not isinstance(item, dict):
            raise ConfigurationError("Each repository entry must be an object")
        if "pattern" in item:
            pattern = str(item.get("pattern", "")).strip()
            parts = pattern.split("/")
            if len(parts) != 2 or not all(parts) or "\\" in pattern:
                raise ConfigurationError(f"Invalid repository pattern: {pattern!r}")
            patterns.append(pattern)
        else:
            repositories.append(_repository_config(item, root))
    return repositories, patterns


DEFAULT_OIDC_SCOPES = "openid email profile"
DEFAULT_OIDC_BUTTON_LABEL = "Sign in with single sign-on"


def _absolute_http_url(name: str, value: str) -> urlparse.ParseResult:
    parsed = urlparse.urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ConfigurationError(f"{name} must be an absolute http(s) URL")
    if parsed.username or parsed.password or parsed.fragment:
        raise ConfigurationError(f"{name} must not contain credentials or a fragment")
    return parsed


def _decode_jwt_secret(value: str) -> bytes:
    text = value.strip()
    padded = text + "=" * (-len(text) % 4)
    try:
        if "-" in text or "_" in text:
            secret = base64.urlsafe_b64decode(padded)
        else:
            secret = base64.b64decode(padded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ConfigurationError("JWT_SECRET must be base64-encoded") from exc
    if len(secret) < 32:
        raise ConfigurationError("JWT_SECRET must decode to at least 32 bytes (e.g. `openssl rand -base64 32`)")
    return secret


def load_oauth_settings(root: Path) -> OAuthSettings | None:
    """Load the optional OAuth/OIDC configuration. Unset/empty OIDC_ISSUER turns the feature off."""
    issuer = os.getenv("OIDC_ISSUER", "").strip()
    if not issuer:
        return None

    public_url_value = os.getenv("PERSONAL_REPO_MCP_PUBLIC_URL", "").strip().rstrip("/")
    if not public_url_value:
        raise ConfigurationError("PERSONAL_REPO_MCP_PUBLIC_URL must be set when OIDC_ISSUER is set")
    public_url = _absolute_http_url("PERSONAL_REPO_MCP_PUBLIC_URL", public_url_value)
    if public_url.query or public_url.params:
        raise ConfigurationError("PERSONAL_REPO_MCP_PUBLIC_URL must not contain a query")
    # The public URL is the production switch: an https:// deployment is production.
    production = public_url.scheme == "https"

    parsed_issuer = _absolute_http_url("OIDC_ISSUER", issuer)
    if production and parsed_issuer.scheme != "https":
        raise ConfigurationError("OIDC_ISSUER must use https:// when PERSONAL_REPO_MCP_PUBLIC_URL is https://")

    client_id = os.getenv("OIDC_CLIENT_ID", "").strip()
    if not client_id:
        raise ConfigurationError("OIDC_CLIENT_ID must be set when OIDC_ISSUER is set")
    client_secret = _read_secret("OIDC_CLIENT_SECRET", "OIDC_CLIENT_SECRET_FILE", required=False)

    scopes = " ".join(os.getenv("OIDC_SCOPES", "").split()) or DEFAULT_OIDC_SCOPES
    if "openid" not in scopes.split(" "):
        raise ConfigurationError("OIDC_SCOPES must contain 'openid'")

    button_label = os.getenv("OIDC_BUTTON_LABEL", "").strip() or DEFAULT_OIDC_BUTTON_LABEL

    jwt_secret_text = _read_secret("JWT_SECRET", "JWT_SECRET_FILE")
    assert jwt_secret_text is not None
    jwt_secret = _decode_jwt_secret(jwt_secret_text)

    db_value = os.getenv("PERSONAL_REPO_MCP_OAUTH_DB", "").strip()
    database_path = Path(db_value) if db_value else root.parent / "data" / "oauth.sqlite"

    return OAuthSettings(
        public_url=public_url_value,
        jwt_secret=jwt_secret,
        oidc_issuer=issuer,
        oidc_client_id=client_id,
        oidc_client_secret=client_secret,
        oidc_scopes=scopes,
        oidc_button_label=button_label,
        database_path=database_path.resolve(),
        production=production,
    )


def load_settings() -> Settings:
    root = Path(os.getenv("PERSONAL_REPO_MCP_ROOT", "/srv/personal-repo-mcp/repositories")).resolve()
    root.mkdir(parents=True, exist_ok=True)
    config_path = Path(os.getenv("PERSONAL_REPO_MCP_CONFIG", "/etc/personal-repo-mcp/repositories.json"))
    raw = _load_repository_config(config_path, os.getenv("PERSONAL_REPO_MCP_REPOSITORIES", "[]"))
    repositories, patterns = _parse_entries(raw, root)
    ids = [repo.id for repo in repositories]
    if len(ids) != len(set(ids)):
        raise ConfigurationError("Repository ids must be unique")
    git_backend = os.getenv("PERSONAL_REPO_MCP_GIT_BACKEND", "git").strip().lower()
    if git_backend not in {"git", "hot-git"}:
        raise ConfigurationError("PERSONAL_REPO_MCP_GIT_BACKEND must be 'git' or 'hot-git'")
    try:
        port = int(os.getenv("PERSONAL_REPO_MCP_PORT", "8000"))
    except ValueError as exc:
        raise ConfigurationError("PERSONAL_REPO_MCP_PORT must be an integer") from exc
    if not 1 <= port <= 65535:
        raise ConfigurationError("PERSONAL_REPO_MCP_PORT must be between 1 and 65535")
    token = _read_secret("PERSONAL_REPO_MCP_TOKEN", "PERSONAL_REPO_MCP_TOKEN_FILE")
    github_pat = _read_secret("PERSONAL_REPO_MCP_GITHUB_PAT", "PERSONAL_REPO_MCP_GITHUB_PAT_FILE")
    assert token is not None
    assert github_pat is not None
    oauth = load_oauth_settings(root)
    return Settings(
        host=os.getenv("PERSONAL_REPO_MCP_HOST", "127.0.0.1"),
        port=port,
        token=token,
        github_pat=github_pat,
        git_backend=git_backend,
        allowed_hosts=_csv(os.getenv("PERSONAL_REPO_MCP_ALLOWED_HOSTS", ""), ("127.0.0.1:*", "localhost:*", "[::1]:*")),
        allowed_origins=_csv(os.getenv("PERSONAL_REPO_MCP_ALLOWED_ORIGINS", ""), ("http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*")),
        repository_root=root,
        repositories=tuple(repositories),
        repository_patterns=tuple(sorted(set(patterns))),
        oauth=oauth,
    )
