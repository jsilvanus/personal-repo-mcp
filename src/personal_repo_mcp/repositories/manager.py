from __future__ import annotations

import fnmatch
import subprocess
from pathlib import Path

from ..config import RepositoryConfig
from ..git.auth import git_environment
from ..git.backend import HotGitBackend, RepositoryBackend
from .model import Repository
from .paths import RepositoryPathError, ensure_contained


class RepositoryError(RuntimeError):
    """Raised when a repository cannot be prepared or accessed."""


class RepositoryManager:
    """Owns stable workspaces, allow-list enforcement, and optional hot-git workers."""

    def __init__(
        self,
        root: Path,
        configs: tuple[RepositoryConfig, ...],
        patterns: tuple[str, ...] = (),
        backend: str = "git",
    ):
        self._root = root.resolve()
        self._patterns = tuple(patterns)
        if backend not in {"git", "hot-git"}:
            raise RepositoryError(f"Unsupported Git backend: {backend}")
        self._backend = backend
        self._hot_backends: dict[str, HotGitBackend] = {}
        self._repositories = {
            config.id: Repository(id=config.id, name=config.name, remote=config.remote, workspace=config.workspace)
            for config in configs
        }

    @property
    def root(self) -> Path:
        return self._root

    @property
    def backend_name(self) -> str:
        return self._backend

    def list(self) -> list[Repository]:
        return sorted(self._repositories.values(), key=lambda repo: repo.id)

    def get(self, repository_id: str) -> Repository:
        try:
            return self._repositories[repository_id]
        except KeyError as exc:
            raise RepositoryError(f"Unknown repository: {repository_id}") from exc

    def is_allowed(self, repository_id: str) -> bool:
        return repository_id in self._repositories or any(
            fnmatch.fnmatchcase(repository_id, pattern) for pattern in self._patterns
        )

    def allowed_patterns(self) -> tuple[str, ...]:
        return self._patterns

    def backend(self, repository_id: str) -> RepositoryBackend:
        repository = self.get(repository_id)
        if not repository.initialized:
            raise RepositoryError(f"Repository is not prepared: {repository_id}")
        if self._backend == "git":
            from ..git.backend import GitBackend

            return GitBackend(repository.workspace)
        hot = self._hot_backends.get(repository_id)
        if hot is None:
            hot = HotGitBackend.open(repository.workspace)
            self._hot_backends[repository_id] = hot
        return hot

    def close(self) -> None:
        backends = list(self._hot_backends.values())
        self._hot_backends.clear()
        for backend in backends:
            backend.close()

    def prepare_all(self) -> None:
        for repository in self.list():
            self.prepare(repository.id)

    def prepare(self, repository_id: str) -> Repository:
        repository = self.get(repository_id)
        return self._clone_or_validate(repository)

    def clone(self, repository_id: str) -> Repository:
        """Clone an allowed GitHub OWNER/REPOSITORY into persistent storage."""
        if not self._valid_remote_id(repository_id):
            raise RepositoryError("Repository must use the GitHub OWNER/REPOSITORY form")
        if not self.is_allowed(repository_id):
            raise RepositoryError(f"Repository is not allowed: {repository_id}")

        existing = self._repositories.get(repository_id)
        if existing is not None:
            return self._clone_or_validate(existing)

        owner, name = repository_id.split("/", 1)
        workspace = (self._root / owner / name).resolve()
        try:
            ensure_contained(self._root, workspace)
        except RepositoryPathError as exc:
            raise RepositoryError(str(exc)) from exc
        repository = Repository(
            id=repository_id,
            name=name,
            remote=f"https://github.com/{owner}/{name}.git",
            workspace=workspace,
        )
        self._repositories[repository_id] = repository
        try:
            return self._clone_or_validate(repository)
        except Exception:
            self._repositories.pop(repository_id, None)
            raise

    def _clone_or_validate(self, repository: Repository) -> Repository:
        try:
            workspace = ensure_contained(self._root, repository.workspace)
        except RepositoryPathError as exc:
            raise RepositoryError(str(exc)) from exc
        workspace.parent.mkdir(parents=True, exist_ok=True)
        if repository.initialized:
            return repository
        if workspace.exists() and any(workspace.iterdir()):
            raise RepositoryError(f"Workspace exists and is not a Git repository: {workspace}")
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

    @staticmethod
    def _valid_remote_id(repository_id: str) -> bool:
        parts = repository_id.split("/")
        return len(parts) == 2 and all(parts) and all(part not in {".", ".."} for part in parts)
