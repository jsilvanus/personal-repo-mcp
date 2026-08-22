from personal_repo_mcp.mcp.prompts import register_prompts

from mcp.server import MCPServer


async def _get_prompt(name: str):
    server = MCPServer(name="test")
    register_prompts(server)
    return await server.get_prompt(name, None)


def _resource_and_text(messages):
    resource = next(message.content for message in messages if isinstance(message.content, dict) and message.content.get("type") == "resource")
    text = next(message.content for message in messages if isinstance(message.content, str))
    return resource, text


async def test_setup_prompt_embeds_help_index():
    result = await _get_prompt("setup")
    resource, text = _resource_and_text(result)
    assert resource["resource"]["uri"] == "mcp://help/index"
    assert resource["resource"]["mimeType"] == "text/markdown"
    assert "Personal Repo MCP" in resource["resource"]["text"]
    assert "mcp://help/repositories" in text


async def test_development_prompt_embeds_help_index():
    result = await _get_prompt("development")
    resource, text = _resource_and_text(result)
    assert resource["resource"]["uri"] == "mcp://help/index"
    assert resource["resource"]["mimeType"] == "text/markdown"
    assert "mcp://help/files" in text
    assert "mcp://help/git" in text
