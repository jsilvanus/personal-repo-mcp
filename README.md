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
    | clone_repository("jsilvanus/project")
    v
persistent workspace
```

`mcp-config add repo` never clones a repository and never creates a workspace.

## Features

- Multiple repositories in one MCP server.
- Repository allow-list entries, including GitHub `OWNER/*` patterns.
- Agent-controlled cloning of repositories permitted by the allow-list.
- Full and chunked file reads.
- File writes and line-oriented edits.
- Standard unified-diff application.
- Persistent workspaces, including untracked files.
- Optimistic writes using content hashes.
- Git status, diff, staging, commit, branch, checkout, reset, merge/rebase, and conflict operations.
- Repository-scoped `chain_command`.
- MCP Resources and resource subscriptions.
- Nested Git repositories/submodules are readable but cannot be modified through the parent repository context.
- Streamable HTTP transport.
- Bearer authentication for MCP clients.
- Separate GitHub PAT for Git operations.
- Central outbound secret scrubbing.
- Non-root Docker deployment with dropped capabilities and `no-new-privileges`.

Test/build execution and MCP Tasks are intentionally not part of the current runtime.

## Resources

The resource model separates stable information from independently changing state:

```text
system://info
system://storage
system://repositories

repo://<repository>/info
repo://<repository>/storage
repo://<repository>/file/<path>
repo://<repository>/git/status
repo://<repository>/git/diff
repo://<repository>/git/conflicts
repo://<repository>/tests/<run-id>       # reserved
repo://<repository>/artifacts/<id>      # reserved
```

`system://info` contains stable server/container information such as version, transport, effective CPU count, and memory limit. Ordinary file changes do not invalidate it.

`system://storage` reports current storage usage for the persistent workspace. It can change as repository files are created, modified, cloned, or deleted.

`system://repositories` is a list of repository descriptors. It includes concrete managed repositories and administrator-approved selectors that have not necessarily been cloned yet. Cloning an allowed repository changes this resource; ordinary file edits do not.

Repository-specific information and storage are separate from Git state. A file notification is scoped to the changed file and the Git resources affected by that change rather than invalidating the basic system information or repository list.

Resource subscriptions therefore let an agent watch exactly the state it cares about. Notifications are change signals; the client reads the resource again to obtain the current value.

## Repository allow-list administration

After installing the package, the host administrator uses the `mcp-config` command. It modifies the host-side configuration only.

```bash
mcp-config pat
mcp-config pat "$GITHUB_PAT"
mcp-config add repo jsilvanus/my-project
mcp-config add repo jsilvanus/*
mcp-config list repo
mcp-config remove repo jsilvanus/my-project
```

The wildcard is a **GitHub repository selector**, not a filesystem wildcard. The CLI never clones repositories.

The administrator's allow-list is intentionally not an MCP operation. An agent cannot grant itself access to another repository by changing server configuration.

## Configuration

Production configuration is kept outside the repository workspace:

```text
/etc/personal-repo-mcp/
    repositories.json
    secrets/
        mcp-token
        github-pat

/srv/personal-repo-mcp/
    repositories/
        owner/
            project/
```

`repositories.json` is versioned JSON. It can contain concrete repositories and selectors:

```json
{
  "version": 1,
  "repositories": [
    { "pattern": "jsilvanus/*" },
    {
      "id": "other/project",
      "name": "project",
      "remote": "https://github.com/other/project.git",
      "workspace": "other/project"
    }
  ]
}
```

A pattern authorizes cloning but does not imply that a workspace already exists.

## MCP repository lifecycle

The agent can request:

```text
clone_repository("jsilvanus/project")
```

The server verifies that `jsilvanus/project` matches an administrator-approved selector, then clones it into persistent storage. The allow-list is not changed.

Once cloned, the repository is available to the normal filesystem, Git, chain, and resource operations.

## Deployment

The intended production deployment is **one Docker container for the whole MCP**, not one container per repository.

### Quick VPS setup

1. Install Docker and Compose.
2. Clone this repository.
3. Create the host configuration and secret directories:

```bash
sudo mkdir -p /etc/personal-repo-mcp/secrets
sudo mkdir -p /srv/personal-repo-mcp/repositories
```

4. Install the package/CLI on the host:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

5. Configure the GitHub PAT and repository allow-list:

```bash
mcp-config pat
mcp-config add repo jsilvanus/*
```

6. Create the MCP bearer-token secret at `/etc/personal-repo-mcp/secrets/mcp-token`. The GitHub PAT is stored by `mcp-config` at `/etc/personal-repo-mcp/secrets/github-pat`.

7. Start the server:

```bash
docker compose up -d --build
```

8. Check it:

```bash
docker compose ps
curl http://127.0.0.1:8000/healthz
docker compose logs -f
```

The MCP port is deliberately bound to localhost. Put HTTPS termination and public access in an existing reverse proxy such as Caddy or nginx, proxying to `http://127.0.0.1:8000`.

## Authentication and secrets

There are two independent credentials:

1. **MCP token** — authenticates MCP clients.
2. **GitHub PAT** — authenticates GitHub operations.

The GitHub PAT is supplied to Git through `GIT_ASKPASS` and is not embedded in remote URLs. MCP responses and errors pass through central secret scrubbing.

Keep credentials out of `repositories.json` and never commit them.

## Security model

```text
MCP bearer token
        |
authenticated client
        |
repository selector / id
        |
repositories.json allow-list
        |
path containment + repository boundaries
        |
persistent workspace
```

The GitHub PAT is a separate credential path. Docker is the deployment boundary; the allow-list and filesystem validation are the application authorization boundary.

The current MCP API has no generic shell command and no test/build execution. Do not treat the container as a sandbox for arbitrary repository code. Adding code execution later requires a separate sandbox/resource-limit design.

## Submodules and nested repositories

Nested Git repositories and submodules may be read through the parent workspace, but filesystem writes through the parent repository context are rejected. A future version may register nested repositories independently.

## Development

The project targets Python 3.11+ and uses MCP Python SDK 2.x.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
pytest
```

## Roadmap

- CI/regression workflow.
- Test/build execution with proper sandboxing.
- Artifact resources and download mechanisms.
- Filesystem watchers for external changes.
- More complete nested-repository management.
- MCP Tasks when SDK/client support is sufficiently mature.

## License

European Union Public Licence 1.2 (EUPL-1.2).
