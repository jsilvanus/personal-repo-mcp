from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Repository:
    """A managed repository with a server-owned workspace."""

    id: str
    name: str
    remote: str
    workspace: Path

    @property
    def exists(self) -> bool:
        return self.workspace.exists()

    @property
    def git_dir(self) -> Path:
        return self.workspace / ".git"

    @property
    def initialized(self) -> bool:
        return self.git_dir.exists()

    def summary(self) -> dict[str, object]:
        return {
            "id": self.id,
            "name": self.name,
            "remote": self.remote,
            "initialized": self.initialized,
        }
