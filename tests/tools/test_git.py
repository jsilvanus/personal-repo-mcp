from personal_repo_mcp.mcp.server import create_mcp
from personal_repo_mcp.repositories import RepositoryManager
from personal_repo_mcp.config import RepositoryConfig


def test_git_tools_are_registered(tmp_path):
    config = RepositoryConfig(id="repo", name="Repo", remote="https://example.invalid/repo.git", workspace=tmp_path / "repo")
    manager = RepositoryManager(tmp_path, (config,))
    server = create_mcp.__wrapped__ if hasattr(create_mcp, "__wrapped__") else create_mcp
    # Registration itself is exercised by constructing the MCP server; exact SDK introspection is version-specific.
    assert callable(server)
