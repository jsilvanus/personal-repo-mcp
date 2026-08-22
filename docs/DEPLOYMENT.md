# Production deployment

The intended MVP deployment is one Docker container containing the MCP server and all configured repository workspaces. There is no Docker-per-repository model and no orchestration layer.

## Host layout

```text
/etc or deployment directory
├── config/repositories.json   # repository allow-list; mounted read-only
├── .env                        # MCP token + GitHub PAT; never commit
└── repositories/               # persistent Git workspaces; never commit
```

The repository configuration is mounted into the container as `/etc/personal-repo-mcp/repositories.json`. Repository workspaces are mounted at `/srv/personal-repo-mcp/repositories`.

## Repository configuration

Use `config/repositories.example.json` as the template. The production file uses a versioned object:

```json
{
  "version": 1,
  "repositories": [
    {
      "id": "my-project",
      "name": "My project",
      "remote": "https://github.com/example/my-project.git",
      "workspace": "my-project"
    }
  ]
}
```

Repository IDs are the only repository selectors exposed to MCP clients. The configured workspace must remain below the configured repository root. The configuration therefore acts as the repository allow-list; filesystem containment checks enforce the boundary.

Do not put credentials in this JSON file.

## Credentials

There are two separate credentials:

- `PERSONAL_REPO_MCP_TOKEN`: bearer token used by MCP clients to authenticate to the server.
- `PERSONAL_REPO_MCP_GITHUB_PAT`: GitHub personal access token used by Git for HTTPS clone/fetch/pull/push operations.

The GitHub PAT is passed to Git through `GIT_ASKPASS`; it is never inserted into a repository URL or written into repository configuration. `GIT_TERMINAL_PROMPT=0` prevents Git from hanging for interactive credentials.

Use a GitHub PAT with only the repository permissions required by the repositories this server manages.

## Compose deployment

Set the required variables in a host-only `.env` file or export them in the deployment environment:

```text
PERSONAL_REPO_MCP_TOKEN=<random-long-server-token>
PERSONAL_REPO_MCP_GITHUB_PAT=<github-pat>
PERSONAL_REPO_MCP_ALLOWED_HOSTS=mcp.example.com
PERSONAL_REPO_MCP_ALLOWED_ORIGINS=https://mcp.example.com
```

Then:

```text
mkdir -p config repositories
after copying config/repositories.example.json to config/repositories.json

docker compose up -d --build
```

The container listens on `127.0.0.1:8000` on the host. Put an HTTPS reverse proxy in front of it for Internet access. Do not publish the MCP port directly to the Internet.

## Health

`GET /healthz` is unauthenticated and is intended for Docker/reverse-proxy health checks. MCP itself is mounted at `/mcp` and remains bearer-token protected.

## Persistence and backup

The `repositories/` host directory is the persistent workspace. It contains changes that may not yet have been pushed upstream, including untracked files. Back it up independently of GitHub. Recovery should restore the directory before starting the container.

## Security model

The security boundary is layered:

1. MCP bearer token authenticates the client.
2. `repositories.json` allow-lists repository IDs and their workspace locations.
3. Path containment prevents a repository workspace from escaping the configured root.
4. File operations reject writes into nested Git repositories when accessed through a parent repository.
5. Docker runs the application as an unprivileged user with `no-new-privileges` and all Linux capabilities dropped.
6. Host/Origin validation protects the Streamable HTTP endpoint against DNS-rebinding and unwanted browser origins.

The host should also protect the `.env`, repository configuration, and persistent repository directory with normal filesystem permissions.

## Not included yet

This deployment intentionally does not introduce Docker orchestration, per-repository containers, a database, a remote artifact store, or automatic filesystem watching. Those can be added later without changing the single-container repository model.
