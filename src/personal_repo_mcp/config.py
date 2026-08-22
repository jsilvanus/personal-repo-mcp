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
    """Configuration for one managed Git repository."""

    id: str
    name: str
    remote: str
    workspace: Path


@dataclass(frozen=True, slots=True)
class Settings:
    """Application configuration loaded from environment variables."""

    host: str
    port: int
    token: str | None
    repositories: tuple[RepositoryConfig, ...]


def _repository_config(raw: Any, root: Path) -> RepositoryConfig:
    if not isinstance(raw, dict):
        raise ConfigurationError("Each repository must be an object")

    repo_id = str(raw.get("id", "")).strip()
    name = str(raw.get("name", repo_id)).strip()
    remote = str(raw.get("remote", "")).strip()
    workspace_value = str(raw.get("workspace", "")).strip()

    if not repo_id or not name or not remote or not workspace_value:
        raise ConfigurationError("Repository requires id, name, remote and workspace")
    if "/" in repo_id or "\\" in repo_id or repo_id in {".", ".."}:
        raise ConfigurationError(f"Invalid repository id: {repo_id!r}")

    workspace = Path(workspace_value)
    if not workspace.is_absolute():
        workspace = root / workspace
    workspace = workspace.resolve()
    if workspace == root or root not in workspace.parents:
        raise ConfigurationError(
            f"Repository workspace must be below repository root: {workspace}"
        )

    return RepositoryConfig(id=repo_id, name=name, remote=remote, workspace=workspace)


def load_settings() -> Settings:
    root = Path(os.getenv("PERSONAL_REPO_MCP_ROOT", "/srv/personal-repo-mcp/repositories")).resolve()
    root.mkdir(parents=True, exist_ok=True)

    config_path = Path(
        os.getenv("PERSONAL_REPO_MCP_CONFIG", "/etc/personal-repo-mcp/repositories.json")
    )

    if config_path.exists():
        try:
            raw = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ConfigurationError(f"Cannot read repository configuration: {config_path}") from exc
    else:
        inline = os.getenv("PERSONAL_REPO_MCP_REPOSITORIES", "[]")
        try:
            raw = json.loads(inline)
        except json.JSONDecodeError as exc:
            raise ConfigurationError("PERSONAL_REPO_MCP_REPOSITORIES is not valid JSON") from exc

    if not isinstance(raw, list):
        raise ConfigurationError("Repository configuration must be a JSON array")

    repositories = tuple(_repository_config(item, root) for item in raw)
    ids = [repo.id for repo in repositories]
    if len(ids) != len(set(ids)):
        raise ConfigurationError("Repository ids must be unique")

    try:
        port = int(os.getenv("PERSONAL_REPO_MCP_PORT", "8000"))
    except ValueError as exc:
        raise ConfigurationError("PERSONAL_REPO_MCP_PORT must be an integer") from exc
    if not 1 <= port <= 65535:
        raise ConfigurationError("PERSONAL_REPO_MCP_PORT must be between 1 and 65535")

    token = os.getenv("PERSONAL_REPO_MCP_TOKEN")
    if not token:
        raise ConfigurationError(
            "PERSONAL_REPO_MCP_TOKEN must be set for the remote HTTP server"
        )

    return Settings(
        host=os.getenv("PERSONAL_REPO_MCP_HOST", "127.0.0.1"),
        port=port,
        token=token,
        repositories=repositories,
    )
