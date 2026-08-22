from pathlib import Path
import subprocess

from personal_repo_mcp.config import RepositoryConfig
from personal_repo_mcp.repositories import RepositoryManager


def test_repository_manager_lists_and_resolves_by_id(tmp_path: Path) -> None:
    config = RepositoryConfig(
        id="demo",
        name="Demo",
        remote="https://example.invalid/demo.git",
        workspace=tmp_path / "demo",
    )
    manager = RepositoryManager(tmp_path, (config,))

    assert [repo.id for repo in manager.list()] == ["demo"]
    assert manager.get("demo").workspace == tmp_path / "demo"


def test_hot_git_backend_is_reused_and_closed(tmp_path: Path) -> None:
    workspace = tmp_path / "demo"
    workspace.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=workspace, check=True)
    config = RepositoryConfig(
        id="demo",
        name="Demo",
        remote="https://example.invalid/demo.git",
        workspace=workspace,
    )
    manager = RepositoryManager(tmp_path, (config,), backend="hot-git")

    first = manager.backend("demo")
    second = manager.backend("demo")
    assert first is second

    manager.close()
    assert manager._hot_backends == {}
