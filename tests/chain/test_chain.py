import pytest

from personal_repo_mcp.chain.executor import ChainExecutor
from personal_repo_mcp.chain.model import ChainCommand, ChainPolicy


class FakeResult:
    def __init__(self, error=False, structured=None):
        self.is_error = error
        self.content = []
        self.structured_content = structured if structured is not None else {"ok": not error}


class FakeMcp:
    def __init__(self, results=None):
        self.calls = []
        self.results = list(results or [])

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        if self.results:
            return self.results.pop(0)
        return FakeResult()


@pytest.mark.asyncio
async def test_chain_injects_repository_once():
    mcp = FakeMcp()
    executor = ChainExecutor(mcp)
    result = await executor.execute("repo", [ChainCommand("git_status", {})], ChainPolicy())
    assert result[0]["is_error"] is False
    assert mcp.calls == [("git_status", {"repository": "repo"})]


@pytest.mark.asyncio
async def test_chain_rejects_nested_repository():
    mcp = FakeMcp()
    executor = ChainExecutor(mcp)
    with pytest.raises(ValueError, match="must not specify repository"):
        await executor.execute("repo", [ChainCommand("git_status", {"repository": "other"})], ChainPolicy())


@pytest.mark.asyncio
async def test_chain_rejects_recursion():
    mcp = FakeMcp()
    executor = ChainExecutor(mcp)
    with pytest.raises(ValueError, match="cannot be used"):
        await executor.execute("repo", [ChainCommand("chain_command", {})], ChainPolicy())


@pytest.mark.asyncio
async def test_chain_carries_hot_git_commit_to_next_edit_and_read():
    first_commit = "a" * 40
    second_commit = "b" * 40
    mcp = FakeMcp(
        [
            FakeResult(structured={"commit": first_commit, "ref": "refs/heads/main"}),
            FakeResult(structured={"commit": second_commit, "ref": "refs/heads/main"}),
            FakeResult(structured={"content": "hello"}),
        ]
    )
    executor = ChainExecutor(mcp)
    commands = [
        ChainCommand("git_edit", {"changes": [{"path": "a.txt", "content": "one"}], "message": "one"}),
        ChainCommand("git_edit", {"changes": [{"path": "a.txt", "content": "two"}], "message": "two"}),
        ChainCommand("git_read_file", {"path": "a.txt"}),
    ]

    result = await executor.execute("repo", commands, ChainPolicy())

    assert len(result) == 3
    assert mcp.calls[0][1] == {
        "changes": [{"path": "a.txt", "content": "one"}],
        "message": "one",
        "repository": "repo",
    }
    assert mcp.calls[1][1]["expected_ref"] == first_commit
    assert mcp.calls[1][1]["repository"] == "repo"
    assert mcp.calls[2][1]["revision"] == second_commit
    assert mcp.calls[2][1]["repository"] == "repo"


@pytest.mark.asyncio
async def test_chain_preserves_explicit_chain_base():
    first_commit = "a" * 40
    explicit = "c" * 40
    mcp = FakeMcp([
        FakeResult(structured={"commit": first_commit}),
        FakeResult(structured={"commit": "b" * 40}),
    ])
    executor = ChainExecutor(mcp)
    await executor.execute(
        "repo",
        [
            ChainCommand("git_edit", {"changes": [{"path": "a", "content": "1"}], "message": "one"}),
            ChainCommand("git_edit", {"changes": [{"path": "a", "content": "2"}], "message": "two", "expected_ref": explicit}),
        ],
        ChainPolicy(),
    )
    assert mcp.calls[1][1]["expected_ref"] == explicit
