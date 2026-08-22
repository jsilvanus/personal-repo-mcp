# personal-repo-mcp

A self-hosted, multi-repository MCP server for AI agents. It gives an agent a persistent Git workspace on your own VPS, with controlled read/write access to configured repositories and normal Git operations.

The goal is deliberately simple: **let an AI work on repositories locally on your server, and push to GitHub when the work is ready.**

## Status

This project is an MVP intended for personal/self-hosted use. The core repository, filesystem, Git, resource, authentication, and Docker deployment features are implemented. Test/build execution and MCP Tasks are intentionally not part of the current runtime.

## Features

### Repository and filesystem operations

- Multiple repositories in one MCP server.
- Repository IDs are explicitly configured in an allow-list.
- Full file reads.
- Chunked/partial file reads for large files.
- File writes.
- Line-oriented insert, replace, and delete operations.
- Standard unified-diff application.
- Persistent workspace files, including untracked Git files.
- Optimistic writes using content hashes to detect stale changes.
- Nested Git repositories/submodules can be read but cannot be modified through the parent repository context.

### Git operations

- Status.
- Diff.
- Add/stage and commit operations.
- Branch operations.
- Checkout and reset operations.
- Merge/rebase operations.
- Conflict inspection.
- Repository-scoped command chaining with `chain_command`.

`chain_command` is intentionally scoped to one repository. A chain does not change the MCP protocol; it is a single tool call containing a sequence of repository operations whose results can be inspected individually.

### MCP Resources

Resources expose persistent repository state using a stable `repo://` namespace:

```text
repo://<repository>/file/<path>
repo://<repository>/git/status
repo://<repository>/git/diff
repo://<repository>/git/conflicts
repo://<repository>/tests/<run-id>       # reserved
repo://<repository>/artifacts/<id>      # reserved
```

File resources include untracked files and expose content/version information. Git resources expose current repository state.

Resource subscriptions allow clients to observe changes without polling. Resource notifications are change signals; clients read the resource again to obtain the current state.

### Security and deployment

- Streamable HTTP MCP transport for remote VPS deployment.
- Bearer-token authentication for MCP clients.
- Separate GitHub PAT for GitHub access.
- Central outbound secret scrubbing for MCP results and errors.
- Repository allow-list and path containment checks.
- Nested Git repository write protection.
- Non-root Docker runtime.
- Dropped Linux capabilities and `no-new-privileges`.
- Persistent repository storage.
- Host-mounted configuration and secret files.
- Docker healthcheck and graceful shutdown configuration.

## Architecture

The intended deployment is one container, not one container per repository:

```text
                         Internet
                            |
                       HTTPS proxy
                            |
                     127.0.0.1:8000
                            |
                 +----------------------+
                 | personal-repo-mcp    |
                 |                      |
                 | Python + MCP SDK     |
                 | Git                  |
                 | all configured repos |
                 +----------+-----------+
                            |
                    persistent storage
                            |
                 /srv/.../repositories/
```

Repository isolation is enforced by the MCP application and filesystem path validation. Docker is the deployment boundary, not the repository authorization model.

## Configuration

Production configuration is kept outside the repository workspace.

A typical deployment uses:

```text
/etc/personal-repo-mcp/
    repositories.json
    secrets/
        mcp-token
        github-pat

/srv/personal-repo-mcp/
    repositories/
        repo-a/
        repo-b/
```

### Repository configuration

`repositories.json` uses versioned JSON configuration:

```json
{
  "version": 1,
  "repositories": [
    {
      "id": "my-project",
      "path": "/data/repositories/my-project",
      "remote": "https://github.com/example/my-project.git"
    }
  ]
}
```

The repository ID is the identifier exposed to MCP clients. The configured repository path must remain beneath the configured repository root. The agent cannot add arbitrary repositories to its own allow-list.

Keep credentials out of this file.

## Authentication

There are two separate credentials:

1. **MCP token** — authenticates clients connecting to this MCP server.
2. **GitHub PAT** — authenticates Git operations against GitHub.

The GitHub PAT is supplied to Git through `GIT_ASKPASS`; it is not embedded in repository URLs.

Both credentials can be provided as mounted secret files in Docker. Environment variables remain available for non-Docker or migration use.

Never commit either credential to the repository.

## Docker deployment

The repository contains a Dockerfile and Compose configuration for the single-container deployment model.

### 1. Install Docker

Install a current Docker Engine and Docker Compose on the VPS using your distribution's supported packages.

### 2. Clone the server

```bash
git clone https://github.com/jsilvanus/personal-repo-mcp.git
cd personal-repo-mcp
```

### 3. Create the host directories

```bash
sudo mkdir -p /etc/personal-repo-mcp/secrets
sudo mkdir -p /srv/personal-repo-mcp/repositories
sudo chown -R root:root /etc/personal-repo-mcp
```

The repository workspace directory must be writable by the container's runtime user. Follow the ownership/UID requirements in the Compose configuration for the deployment version you are using.

### 4. Create `repositories.json`

For example:

```bash
sudo mkdir -p /etc/personal-repo-mcp
sudo nano /etc/personal-repo-mcp/repositories.json
```

Use the versioned structure described above. Paths in the configuration must correspond to paths inside the container's `/data/repositories` root.

### 5. Create the secrets

Create the MCP token and GitHub PAT as separate files:

```bash
sudo sh -c 'umask 077; printf "%s" "YOUR_MCP_TOKEN" > /etc/personal-repo-mcp/secrets/mcp-token'
sudo sh -c 'umask 077; printf "%s" "YOUR_GITHUB_PAT" > /etc/personal-repo-mcp/secrets/github-pat'
sudo chmod 600 /etc/personal-repo-mcp/secrets/mcp-token /etc/personal-repo-mcp/secrets/github-pat
```

Use a GitHub PAT with only the permissions required by the repositories you intend to manage.

### 6. Prepare repositories

Clone or otherwise populate the configured repositories beneath the persistent repository directory. The container is designed to work with multiple repositories in the same volume.

### 7. Start the container

```bash
docker compose up -d --build
```

Check the service:

```bash
docker compose ps
docker compose logs -f
curl http://127.0.0.1:8000/healthz
```

The MCP port is intentionally bound to localhost by the Compose configuration. Do not expose port 8000 directly to the public Internet.

### 8. Put HTTPS in front of it

Use the VPS's existing reverse proxy (for example Caddy or nginx) to terminate TLS and proxy the MCP endpoint to:

```text
http://127.0.0.1:8000
```

The MCP client should connect to the HTTPS URL exposed by the reverse proxy and send the configured bearer token.

Do not put the GitHub PAT in the reverse-proxy configuration or MCP client configuration. The MCP token and GitHub PAT have different purposes.

### 9. Updates

```bash
git pull
docker compose up -d --build
```

The repository data is stored outside the image, so rebuilding the container does not remove the working repositories.

## Persistence and backups

The repository directory is persistent state. This includes changes that have not been committed or pushed to GitHub, including untracked files.

Back up the persistent repository directory independently of the Docker image. A GitHub remote is not a complete backup of the MCP workspace because uncommitted and untracked work may exist only on the VPS.

Also back up `repositories.json` separately. Keep credential files out of normal backup sets unless your secret-management policy explicitly requires them to be backed up.

## Security model

The security model has several layers:

```text
MCP bearer token
        |
        v
authenticated MCP client
        |
        v
configured repository ID
        |
        v
repositories.json allow-list
        |
        v
path containment / repository boundary checks
        |
        v
persistent workspace
```

GitHub access is a separate credential path:

```text
MCP Git operation
        |
        v
GIT_ASKPASS
        |
        v
GitHub PAT
        |
        v
GitHub remote
```

MCP responses are passed through secret scrubbing so configured credentials are not intentionally returned to clients, including through command output and errors.

### Important: no arbitrary code execution

The current MCP API does **not** provide a generic shell command tool and does not provide repository test/build execution.

Do not treat the current container as a sandbox for untrusted code. If test or build execution is added later, it should have a separate execution/sandboxing design with resource limits and a clear security boundary.

## Submodules and nested repositories

Git submodules and nested Git repositories can exist inside a configured repository. The parent repository can observe their state through normal Git operations, but filesystem writes through the parent repository context are rejected when the target path is inside a nested Git repository.

A future version may register nested repositories independently so they can be modified through their own repository context.

## Development

Install the project with its development dependencies and run the test suite with `pytest`.

The project targets Python 3.11+ and uses the MCP Python SDK 2.x.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
pytest
```

## Roadmap

The current MVP intentionally leaves several capabilities for later work:

- CI/regression workflow.
- Test and build execution with proper sandboxing.
- Artifact resources and download mechanisms.
- Filesystem watchers for changes made outside the MCP process.
- More complete nested-repository/submodule management.
- MCP Tasks when the relevant SDK/client support is sufficiently mature.

The resource namespace already reserves `tests/` and `artifacts/` so these additions do not require changing the basic resource model.

## License

This project is licensed under the **European Union Public Licence 1.2 (EUPL-1.2)**.
