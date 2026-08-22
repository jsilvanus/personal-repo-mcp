from pathlib import Path

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
