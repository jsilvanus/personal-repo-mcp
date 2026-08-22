from pathlib import Path

import pytest

from personal_repo_mcp.git import GitError, GitRunner, create_branch, diff, status


def init_repo(tmp_path: Path) -> Path:
    import subprocess
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
    (root / "file.txt").write_text("one\n", encoding="utf-8")
    subprocess.run(["git", "add", "--", "file.txt"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=root, check=True, capture_output=True)
    return root


def test_status_and_diff(tmp_path: Path):
    root = init_repo(tmp_path)
    (root / "file.txt").write_text("two\n", encoding="utf-8")
    runner = GitRunner(root)
    assert status(runner)["clean"] is False
    assert "-one" in diff(runner)
    assert "+two" in diff(runner)


def test_branch_creation(tmp_path: Path):
    runner = GitRunner(init_repo(tmp_path))
    assert create_branch(runner, "feature/test")["branch"] == "feature/test"
    assert runner.run("branch", "--show-current").strip() == "feature/test"


def test_rejects_non_repository(tmp_path: Path):
    with pytest.raises(GitError):
        GitRunner(tmp_path)
