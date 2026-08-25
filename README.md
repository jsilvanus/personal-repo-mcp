# personal-repo-mcp

A self-hosted, multi-repository MCP server for AI agents. It gives an agent a persistent Git workspace on your own VPS, with controlled access to administrator-approved repositories and normal Git operations.

**Version 1.0.0 — MVP**

## Quick install

The quickest way to run the MVP is the Docker Compose deployment described in [`docs/QUICK_INSTALL.md`](docs/QUICK_INSTALL.md).

In short:

```bash
git clone https://github.com/jsilvanus/personal-repo-mcp.git
cd personal-repo-mcp
cp .env.example .env
mkdir -p config repositories secrets
cp config/repositories.example.json config/repositories.json
printf '%s\n' "$(openssl rand -hex 32)" > secrets/mcp_token
printf '%s\n' 'your-github-pat' > secrets/github_pat
chmod 600 secrets/mcp_token secrets/github_pat
docker compose up -d --build
```

Before starting the container, edit `.env`, `config/repositories.json`, and `secrets/github_pat`. The MCP token is generated locally above; keep it secret. The default Compose deployment binds the MCP endpoint to `127.0.0.1:8000`, so an HTTPS reverse proxy is required for remote access.

For the full production checklist, see [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).

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

The workspace is an ordinary Git repository. GitHub remains an upstream remote; the MCP server is the persistent local workspace and control boundary.

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
- Optional **hot-git** backend for persistent, treeless repository reads and edits

## Git backends

The existing Git command backend remains the default compatibility path.

The new hot-git backend can be enabled with:

```bash
export PERSONAL_REPO_MCP_GIT_BACKEND=hot-git
```

The dependency is declared in `pyproject.toml` and is installed as a normal Python package; it is **not a Git submodule**.

The backend boundary is deliberately small:

```text
MCP tool
   |
   v
Repository backend
   |
   +-- Git backend
   |
   +-- hot-git backend
          |
          +-- persistent object reader
          +-- treeless object/tree/commit edits
          +-- Git CAS ref publication
```

When hot-git is selected, each repository gets one lazily-created long-lived backend instance. It is shared by callers and closed with the server. This keeps the persistent `cat-file --batch` reader alive without creating one process per MCP request.

The first integrated operations are:

- `git_read_file` — read a file from a ref or commit through the configured backend;
- `git_edit` — perform a multi-file treeless edit and publish it with an expected-ref CAS.

The existing Git command tools remain available during the migration. Operations that depend on a working tree or Git's higher-level merge/rebase machinery continue to use the compatibility backend.

### Chained edits

`git_edit` returns the resulting commit. A caller can use that commit as the expected base for the next edit:

```text
A(base=X) -> commit A
B(base=A) -> commit B
C(base=B) -> commit C
```

This is the foundation for integrating the backend with `chain_command` without allowing concurrent writers to silently overwrite each other.

## Deployment

Configure the host with `mcp-config`, then start the single Docker deployment:

```bash
mcp-config pat
mcp-config add repo jsilvanus/*
docker compose up -d --build
```

`mcp-config add repo` changes only the administrator allow-list. It does **not** clone repositories. The agent clones an allowed repository through the MCP when needed.

For hot-git mode, the normal Python dependency installation installs the library. No submodule checkout is required.

See [`docs/QUICK_INSTALL.md`](docs/QUICK_INSTALL.md) for the shortest setup path and [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) for persistent storage, credentials, HTTPS, and configuration details.

## License

EUPL-1.2
