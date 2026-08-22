from __future__ import annotations

import subprocess
from pathlib import Path

from .auth import git_environment


class GitError(RuntimeError):
    def __init__(self, message: str, *, code: int | None = None, stdout: str = "", stderr: str = ""):
        super().__init__(message)
        self.code = code
        self.stdout = stdout
        self.stderr = stderr


class GitRunner:
    """Run Git only inside a repository workspace; never invokes a shell."""

    def __init__(self, workspace: Path):
        self.workspace = workspace.resolve()
        if not self.workspace.is_dir():
            raise GitError(f"Repository workspace does not exist: {self.workspace}")
        if not (self.workspace / ".git").exists():
            raise GitError(f"Not a Git repository: {self.workspace}")

    def run(self, *args: str, check: bool = True) -> str:
        command = ["git", *args]
        try:
            result = subprocess.run(
                command,
                cwd=self.workspace,
                env=git_environment(),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
        except FileNotFoundError as exc:
            raise GitError("git executable is not installed") from exc
        if check and result.returncode:
            detail = (result.stderr or result.stdout).strip()
            raise GitError(detail or f"git exited with code {result.returncode}", code=result.returncode, stdout=result.stdout, stderr=result.stderr)
        return result.stdout

    def run_bytes(self, *args: str, check: bool = True) -> bytes:
        try:
            result = subprocess.run(
                ["git", *args],
                cwd=self.workspace,
                env=git_environment(),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
        except FileNotFoundError as exc:
            raise GitError("git executable is not installed") from exc
        if check and result.returncode:
            raise GitError((result.stderr or result.stdout).decode(errors="replace").strip(), code=result.returncode)
        return result.stdout
