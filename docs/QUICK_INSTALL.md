# Quick install

This is the shortest path to a working self-hosted `personal-repo-mcp` MVP using Docker Compose.

## 1. Get the source

```bash
git clone https://github.com/jsilvanus/personal-repo-mcp.git
cd personal-repo-mcp
```

The current Compose deployment builds the image locally from this checkout. It does not require Python or the project dependencies to be installed on the host.

## 2. Create configuration

```bash
cp .env.example .env
mkdir -p config repositories secrets
cp config/repositories.example.json config/repositories.json
```

Edit `.env` and set the public host/origin that will be accepted by the HTTP endpoint:

```dotenv
PERSONAL_REPO_MCP_ALLOWED_HOSTS=mcp.example.com
PERSONAL_REPO_MCP_ALLOWED_ORIGINS=https://mcp.example.com
```

For a local-only test, use the host/origin values appropriate for the client you are testing with. Do not expose port 8000 directly to the Internet.

## 3. Create the secrets

Generate a strong MCP bearer token:

```bash
printf '%s\n' "$(openssl rand -hex 32)" > secrets/mcp_token
```

Put a GitHub PAT in `secrets/github_pat`:

```bash
printf '%s\n' 'github_pat_here' > secrets/github_pat
```

Then protect both files:

```bash
chmod 600 secrets/mcp_token secrets/github_pat
```

Use a GitHub token with only the repository permissions required by the repositories managed by this server.

## 4. Configure repositories

Edit `config/repositories.json`. For example:

```json
{
  "version": 1,
  "repositories": [
    {
      "id": "my-project",
      "name": "My project",
      "remote": "https://github.com/jsilvanus/my-project.git",
      "workspace": "my-project"
    }
  ]
}
```

The configured repository IDs are the allow-list exposed to MCP clients. Adding a repository to this file does not clone it; the agent clones an allowed repository when it needs to work with it.

Do not put credentials in `repositories.json`.

## 5. Start the server

```bash
docker compose up -d --build
```

Check the container:

```bash
docker compose ps
docker compose logs --tail=100 personal-repo-mcp
```

The health endpoint is available locally at `http://127.0.0.1:8000/healthz`.

MCP is available at `/mcp` and requires the configured bearer token.

## 6. Put HTTPS in front

The default Compose configuration binds port 8000 only to loopback:

```text
127.0.0.1:8000 -> container:8000
```

For remote access, put an HTTPS reverse proxy in front of it and set `PERSONAL_REPO_MCP_ALLOWED_HOSTS` and `PERSONAL_REPO_MCP_ALLOWED_ORIGINS` to the public endpoint. Do not publish the MCP port directly to the Internet.

## Persistent data

The `repositories/` directory is the persistent workspace. It may contain uncommitted and untracked changes, so it should be backed up independently of GitHub.

The `config/repositories.json` file and both secret files are host-side deployment state and should also be protected and backed up according to your operational requirements.

## Troubleshooting

### Container exits immediately

Check the logs:

```bash
docker compose logs personal-repo-mcp
```

The most common configuration problems are missing secret files or missing `PERSONAL_REPO_MCP_ALLOWED_HOSTS` / `PERSONAL_REPO_MCP_ALLOWED_ORIGINS` values.

### Git operations cannot authenticate

Check that `secrets/github_pat` contains a valid GitHub PAT and that it has access to the configured repository. The application passes the credential to Git through `GIT_ASKPASS`; it does not put the token in the repository URL.

### The agent cannot access a repository

Verify that the repository is present in `config/repositories.json` and that its `workspace` remains below the configured repository root. Adding a repository to the allow-list alone does not clone it.

## More detail

For the full production deployment model, security boundary, credential handling, persistence, and reverse-proxy requirements, see [`DEPLOYMENT.md`](DEPLOYMENT.md).
