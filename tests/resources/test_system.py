from pathlib import Path

from personal_repo_mcp.config import RepositoryConfig
from personal_repo_mcp.repositories import RepositoryManager
from personal_repo_mcp.resources.model import (
    system_info_uri,
    system_repositories_uri,
    system_storage_uri,
)
from personal_repo_mcp.resources.system import _repositories


def test_system_resource_uris_are_distinct() -> None:
    assert system_info_uri() == "system://info"
    assert system_storage_uri() == "system://storage"
    assert system_repositories_uri() == "system://repositories"
    assert len({system_info_uri(), system_storage_uri(), system_repositories_uri()}) == 3


def test_repository_resource_lists_concrete_and_allowed_patterns(tmp_path: Path) -> None:
    workspace = tmp_path / "jsilvanus" / "project"
    workspace.mkdir(parents=True)
    (workspace / ".git").mkdir()
    manager = RepositoryManager(
        tmp_path,
        (
            RepositoryConfig(
                id="jsilvanus/project",
                name="project",
                remote="https://github.com/jsilvanus/project.git",
                workspace=workspace,
            ),
        ),
        ("jsilvanus/*",),
    )

    entries = _repositories(manager)

    concrete = next(item for item in entries if item["id"] == "jsilvanus/project")
    pattern = next(item for item in entries if item["id"] == "jsilvanus/*")
    assert concrete["status"] == "cloned"
    assert pattern["status"] == "allowed"
    assert pattern["cloned"] is False
