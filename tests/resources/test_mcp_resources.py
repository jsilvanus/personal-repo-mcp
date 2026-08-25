from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from mcp.server import MCPServer

from personal_repo_mcp.config import RepositoryConfig
from personal_repo_mcp.metrics import Metrics
from personal_repo_mcp.repositories import RepositoryManager
from personal_repo_mcp.resources import register_resources


@pytest.mark.asyncio
async def test_resource_templates_are_registered(tmp_path: Path) -> None:
    workspace = tmp_path / "foo"
    workspace.mkdir()
    subprocess.run(["git", "init", "-q", str(workspace)], check=True)
    (workspace / "README.md").write_text("hello\n", encoding="utf-8")

    manager = RepositoryManager(
        tmp_path,
        (RepositoryConfig("foo", "Foo", "https://example.invalid/foo.git", workspace),),
    )
    server = MCPServer("test")
    register_resources(server, manager, Metrics())

    templates = await server.list_resource_templates()
    uris = {str(template.uri_template) for template in templates}
    assert "repo://{repository}/file/{+path}" in uris
    assert "repo://{repository}/git/status" in uris
    assert "repo://{repository}/git/diff" in uris
    assert "repo://{repository}/git/conflicts" in uris

    contents = await server.read_resource("repo://foo/file/README.md")
    payload = json.loads(contents[0].content)
    assert payload["path"] == "README.md"
    assert payload["content"] == "hello\n"
    assert len(payload["sha256"]) == 64
