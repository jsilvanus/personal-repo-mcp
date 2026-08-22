from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


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
    )
