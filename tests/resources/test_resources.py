from __future__ import annotations

from pathlib import Path

import pytest

from personal_repo_mcp.resources.files import _path
from personal_repo_mcp.resources.model import artifact_uri, file_uri, git_uri
from personal_repo_mcp.resources.model import test_uri as build_test_uri


def test_resource_uri_namespace() -> None:
    assert file_uri("foo", "src/main.py") == "repo://foo/file/src/main.py"
    assert git_uri("foo", "status") == "repo://foo/git/status"
    assert build_test_uri("foo", "123") == "repo://foo/tests/123"
    assert artifact_uri("foo", "abc") == "repo://foo/artifacts/abc"


def test_file_resource_rejects_git_directory(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    with pytest.raises(ValueError):
        _path(tmp_path, ".git/config")


def test_file_resource_rejects_escape(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        _path(tmp_path, "../outside")
