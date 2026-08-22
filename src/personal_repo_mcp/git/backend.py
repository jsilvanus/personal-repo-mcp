from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from hotgit import Change, EditResult, Repository, RepositoryWorker


class BackendError(RuntimeError):
    """Raised when a repository backend cannot complete an operation."""


class RepositoryBackend(Protocol):
    """Common backend boundary for server-side repository operations."""

    def read_file(self, revision: str, path: str) -> bytes: ...

    def edit(
        self,
        ref: str,
        changes: list[Change],
        message: str,
        expected_ref: str | None = None,
    ) -> EditResult: ...


@dataclass
class GitBackend:
    """Compatibility backend that uses the existing Git command layer."""

    workspace: Path

    def read_file(self, revision: str, path: str) -> bytes:
        from .runner import GitRunner

        return GitRunner(self.workspace).run_bytes("show", f"{revision}:{path}")

    def edit(
        self,
        ref: str,
        changes: list[Change],
        message: str,
        expected_ref: str | None = None,
    ) -> EditResult:
        raise BackendError("The compatibility Git backend does not expose the treeless edit API")


@dataclass
class HotGitBackend:
    """Persistent, treeless backend backed by one hot-git worker."""

    worker: RepositoryWorker

    @classmethod
    def open(cls, workspace: Path) -> "HotGitBackend":
        return cls(RepositoryWorker(Repository(workspace)))

    def read_file(self, revision: str, path: str) -> bytes:
        try:
            return self.worker.editor.read_file(revision, path)
        except Exception as exc:
            raise BackendError(str(exc)) from exc

    def edit(
        self,
        ref: str,
        changes: list[Change],
        message: str,
        expected_ref: str | None = None,
    ) -> EditResult:
        try:
            return self.worker.edit(ref, changes, message, expected_ref=expected_ref)
        except Exception as exc:
            raise BackendError(str(exc)) from exc

    def close(self) -> None:
        self.worker.close()
