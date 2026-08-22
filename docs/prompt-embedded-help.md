# Prompt-Embedded Help

## Goal

Make the `setup` and `development` MCP prompts deliver the `mcp://help/index` resource as an embedded resource, rather than merely telling the model to fetch it.

## Design

- Keep `mcp://help/index` as the canonical help resource.
- `prompts/get setup` and `prompts/get development` return their workflow instructions plus an MCP `EmbeddedResource` containing the help index.
- Keep focused help resources (`repositories`, `files`, `git`, `chain-command`, `resources`) as normal resources for progressive disclosure.
- Do not duplicate the help-index Markdown in prompt text.
- Do not change `tools/list` or add capabilities through prompts.

## Compatibility

Use the Python MCP SDK's standard prompt message/resource content types so clients receive the resource through the normal prompt result. Add tests that assert both prompts contain the embedded `mcp://help/index` resource and retain their workflow guidance.
