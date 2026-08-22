from pathlib import Path

import pytest

from personal_repo_mcp.filesystem.paths import NestedRepositoryError, ensure_writable_repository_path, nested_repository_root
from personal_repo_mcp.filesystem.patch import apply_unified_diff
from personal_repo_mcp.filesystem.writer import write_file


def _nested_repo(workspace: Path, *, git_file: bool = False) -> Path:
    nested = workspace / "libs" / "nested"
    nested.mkdir(parents=True)
    marker = nested / ".git"
    if git_file:
        marker.write_text("gitdir: /tmp/example", encoding="utf-8")
    else:
        marker.mkdir()
    return nested


def test_detects_nested_git_directory(tmp_path: Path) -> None:
    workspace = tmp_path / "repo"
    workspace.mkdir()
    nested = _nested_repo(workspace)
    target = nested / "src" / "main.py"
    target.parent.mkdir()
    target.write_text("hello", encoding="utf-8")

    assert nested_repository_root(workspace, target) == nested


def test_detects_submodule_git_file(tmp_path: Path) -> None:
    workspace = tmp_path / "repo"
    workspace.mkdir()
    nested = _nested_repo(workspace, git_file=True)
    target = nested / "main.py"
    target.write_text("hello", encoding="utf-8")

    assert nested_repository_root(workspace, target) == nested


def test_normal_repository_files_remain_writable(tmp_path: Path) -> None:
    workspace = tmp_path / "repo"
    workspace.mkdir()
    target = workspace / "src" / "main.py"

    ensure_writable_repository_path(workspace, target)
    write_file(workspace, "src/main.py", "hello")
    assert target.read_text(encoding="utf-8") == "hello"


def test_nested_repository_file_is_not_writable(tmp_path: Path) -> None:
    workspace = tmp_path / "repo"
    workspace.mkdir()
    nested = _nested_repo(workspace)
    target = nested / "main.py"
    target.write_text("original", encoding="utf-8")

    with pytest.raises(NestedRepositoryError, match="nested Git repository"):
        write_file(workspace, "libs/nested/main.py", "changed")
    assert target.read_text(encoding="utf-8") == "original"


def test_new_file_inside_nested_repository_is_not_writable(tmp_path: Path) -> None:
    workspace = tmp_path / "repo"
    workspace.mkdir()
    _nested_repo(workspace)

    with pytest.raises(NestedRepositoryError, match="nested Git repository"):
        write_file(workspace, "libs/nested/new.py", "blocked")


def test_unified_diff_cannot_modify_nested_repository(tmp_path: Path) -> None:
    workspace = tmp_path / "repo"
    workspace.mkdir()
    nested = _nested_repo(workspace)
    target = nested / "main.py"
    target.write_text("hello\n", encoding="utf-8")

    patch = "@@ -1 +1 @@\n-hello\n+changed\n"
    with pytest.raises(NestedRepositoryError, match="nested Git repository"):
        apply_unified_diff(workspace, "libs/nested/main.py", patch)
    assert target.read_text(encoding="utf-8") == "hello\n"
