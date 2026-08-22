from pathlib import Path
import subprocess

from hotgit import Change

from personal_repo_mcp.git.backend import HotGitBackend


def init_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=path, check=True)
    (path / "README.md").write_text("one\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "initial"], cwd=path, check=True)


def test_hot_git_backend_reads_and_edits_treeless(tmp_path: Path) -> None:
    init_repo(tmp_path)
    backend = HotGitBackend.open(tmp_path)
    try:
        base = backend.worker.editor.refs.get("refs/heads/main")
        assert backend.read_file(base, "README.md") == b"one\n"

        result = backend.edit(
            "refs/heads/main",
            [Change("README.md", b"two\n")],
            "update",
            expected_ref=base,
        )

        assert result.base == base
        assert result.ref == "refs/heads/main"
        assert result.changed_paths == ("README.md",)
        assert backend.read_file(result.commit, "README.md") == b"two\n"
    finally:
        backend.close()
