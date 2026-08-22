from __future__ import annotations

import subprocess
from pathlib import Path

from ..config import RepositoryConfig
from ..git.auth import git_environment
from .model import Repository
from .paths import RepositoryPathError, ensure_contained


class RepositoryError(RuntimeError):
    """Raised when a repository cannot be prepared or accessed."""


class RepositoryManager:
    """Owns the mapping between stable repository ids and VPS workspaces."""

    def __init__(self, root: Path, configs: tuple[RepositoryConfig, ...]):
        self._root = root.resolve()
        self._repositories = {
            config.id: Repository(
                id=config.id,
                name=config.name,
                remote=config.remote,
                workspace=config.workspace,
            )
            for config in configs
        }

    def list(self) -> list[Repository]:
        return sorted(self._repositories.values(), key=lambda repo: repo.id)

    def get(self, repository_id: str) -> Repository:
        try:
            return self._repositories[repository_id]
        except KeyError as exc:
            raise RepositoryError(f"Unknown repository: {repository_id}") from exc

    def prepare_all(self) -> None:
        for repository in self.list():
            self.prepare(repository.id)

    def prepare(self, repository_id: str) -> Repository:
        repository = self.get(repository_id)
        try:
            workspace = ensure_contained(self._root, repository.workspace)
        except RepositoryPathError as exc:
            raise RepositoryError(str(exc)) from exc

        workspace.parent.mkdir(parents=True, exist_ok=True)

        if repository.initialized:
            if repository.workspace.resolve() != workspace:
                raise RepositoryError(f"Repository workspace changed unexpectedly: {workspace}")
            return repository

        if workspace.exists() and any(workspace.iterdir()):
            raise RepositoryError(
                f"Workspace exists and is not a Git repository: {workspace}"
            )

        if workspace.exists() and not any(workspace.iterdir()):
            workspace.rmdir()

        command = ["git", "clone", "--", repository.remote, str(workspace)]
        try:
            subprocess.run(
                command,
                cwd=self._root,
                env=git_environment(),
                check=True,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except FileNotFoundError as exc:
            raise RepositoryError("git executable is not installed") from exc
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or exc.stdout or "git clone failed").strip()
            raise RepositoryError(f"Failed to clone {repository.id}: {detail}") from exc

        return repository
