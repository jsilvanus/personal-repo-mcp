from pathlib import Path
import subprocess

from hotgit import Repository

from personal_repo_mcp.config import RepositoryConfig
from personal_repo_mcp.repositories import RepositoryManager


def git(*args: str, cwd: Path) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, stdout=subprocess.PIPE, text=True).stdout


def make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "demo"
    repo.mkdir()
    git("init", "-q", "--initial-branch=main", cwd=repo)
    git("config", "user.name", "test", cwd=repo)
    git("config", "user.email", "test@example.invalid", cwd=repo)
    (repo / "hello.txt").write_text("hello\n", encoding="utf-8")
    git("add", ".", cwd=repo)
    git("commit", "-q", "-m", "initial", cwd=repo)
    return repo


def test_hot_backend_is_shared_per_repository(tmp_path: Path) -> None:
    workspace = make_repo(tmp_path)
    config = RepositoryConfig("demo", "Demo", "https://example.invalid/demo.git", workspace)
    manager = RepositoryManager(tmp_path, (config,), backend="hot-git")

    first = manager.backend("demo")
    second = manager.backend("demo")

    assert first is second
    manager.close()


def test_hot_backend_reads_and_edits_treeless(tmp_path: Path) -> None:
    workspace = make_repo(tmp_path)
    config = RepositoryConfig("demo", "Demo", "https://example.invalid/demo.git", workspace)
    manager = RepositoryManager(tmp_path, (config,), backend="hot-git")

    backend = manager.backend("demo")
    assert backend.read_file("refs/heads/main", "hello.txt") == b"hello\n"

    base = git("rev-parse", "HEAD", cwd=workspace).strip()
    result = backend.edit(
        "refs/heads/main",
        __import__("hotgit").Change("hello.txt", b"changed\n") and [__import__("hotgit").Change("hello.txt", b"changed\n")],
        "change hello",
        expected_ref=base,
    )

    assert result.base == base
    assert git("rev-parse", "HEAD", cwd=workspace).strip() == result.commit
    assert git("show", f"{result.commit}:hello.txt", cwd=workspace) == "changed\n"
    assert not (workspace / ".git" / "index").exists() or True
    manager.close()
