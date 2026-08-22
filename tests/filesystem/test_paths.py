from pathlib import Path

import pytest

from personal_repo_mcp.filesystem.paths import FileSystemError, resolve_repository_path


def test_path_is_contained(tmp_path: Path) -> None:
    workspace = tmp_path / "repo"
    workspace.mkdir()
    assert resolve_repository_path(workspace, "src/main.py") == workspace / "src/main.py"


def test_parent_escape_is_rejected(tmp_path: Path) -> None:
    workspace = tmp_path / "repo"
    workspace.mkdir()
    with pytest.raises(FileSystemError):
        resolve_repository_path(workspace, "../secret")


def test_absolute_escape_is_rejected(tmp_path: Path) -> None:
    workspace = tmp_path / "repo"
    workspace.mkdir()
    with pytest.raises(FileSystemError):
        resolve_repository_path(workspace, str(tmp_path / "secret"))
