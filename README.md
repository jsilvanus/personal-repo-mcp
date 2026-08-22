# personal-repo-mcp

A self-hosted, multi-repository MCP server for AI agents. It gives an agent a persistent Git workspace on your own VPS, with controlled read/write access to administrator-approved repositories and normal Git operations.

**Version 1.0.0 — MVP**

## Core idea

The administrator controls **what repositories the agent may access**. The agent controls **which allowed repositories it actually clones**.

```text
Administrator
    |
    | mcp-config add repo jsilvanus/*
    v
repositories.json (allow-list)
    |
    v
MCP server
    |
    +-- clone_repository("jsilvanus/project")
    |
    v
persistent workspace
```

## MCP help resources

The server provides modular, MCP-native operational documentation. Start with:

```text
mcp://help/index
```

Focused topics are available at:

```text
mcp://help/repositories
mcp://help/files
mcp://help/git
mcp://help/chain-command
mcp://help/resources
```

The help resources are intentionally separate from `tools/list`: the MCP tool list remains the authoritative API surface, while the help resources provide progressive-disclosure workflow guidance for agents.

## Features

- Persistent multi-repository workspaces
- Administrator-controlled repository allow-list
- GitHub PAT authentication for Git operations
- Streamable HTTP transport
- File reads, line-range reads, writes, line edits, search, and patches
- Git status, diff, history, branches, fetch/pull/push, merge/rebase, and conflict handling
- Single-repository `chain_command` for composing operations
- MCP resources for system, repository, Git, and individual file state
- Resource subscriptions and change notifications
- Secret scrubbing from MCP output
- Git submodule safeguards
- Docker deployment

## Deployment

Configure the host with `mcp-config`, then start the single Docker deployment:

```bash
mcp-config pat
mcp-config add repo jsilvanus/*
docker compose up -d --build
```

`mcp-config add repo` changes only the administrator allow-list. It does **not** clone repositories. The agent clones an allowed repository through the MCP when needed.

See the deployment documentation in `docs/` for persistent storage, credentials, HTTPS, and configuration details.

## License

EUPL-1.2
