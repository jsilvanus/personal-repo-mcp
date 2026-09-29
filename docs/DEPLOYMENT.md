# Production deployment

The intended MVP deployment is one Docker container containing the MCP server and all configured repository workspaces. There is no Docker-per-repository model and no orchestration layer.

## Host layout

```text
/etc or deployment directory
├── config/repositories.json   # repository allow-list; mounted read-only
├── secrets/
│   ├── mcp_token              # MCP bearer token; Docker secret
│   └── github_pat             # GitHub PAT; Docker secret
└── repositories/               # persistent Git workspaces; never commit
```

The repository configuration is mounted into the container as `/etc/personal-repo-mcp/repositories.json`. Repository workspaces are mounted at `/srv/personal-repo-mcp/repositories`. Secret files are mounted by Compose under `/run/secrets/` and are not included in the repository workspace.

Protect the `secrets/` directory with restrictive host permissions (for example, owner-only read access).

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

- MCP bearer token: authenticates MCP clients to the server.
- GitHub personal access token: authenticates Git HTTPS operations against GitHub.

The production Compose deployment supplies both through Docker secrets:

```text
secrets/mcp_token
secrets/github_pat
```

The application reads them using `PERSONAL_REPO_MCP_TOKEN_FILE` and `PERSONAL_REPO_MCP_GITHUB_PAT_FILE`. Direct environment variables with the old names remain supported for non-Docker deployments and migration, but secret files are preferred for production.

The GitHub PAT is passed to Git through `GIT_ASKPASS`; it is never inserted into a repository URL or written into repository configuration. `GIT_TERMINAL_PROMPT=0` prevents Git from hanging for interactive credentials.

Use a GitHub PAT with only the repository permissions required by the repositories this server manages.

## Secret scrubbing

Configured MCP and GitHub credentials are scrubbed from outbound MCP results. Scrubbing recursively handles strings inside dictionaries, lists, and tuples and also handles percent-encoded credential values. This is defense-in-depth: credentials should still never be intentionally placed in repository content or Git URLs.

## Compose deployment

Create the host configuration, persistent workspace directory, and secret files:

```text
mkdir -p config repositories secrets
cp config/repositories.example.json config/repositories.json
printf '%s\n' 'replace-with-a-long-random-mcp-token' > secrets/mcp_token
printf '%s\n' 'replace-with-your-github-pat' > secrets/github_pat
chmod 600 secrets/mcp_token secrets/github_pat
```

Edit `config/repositories.json` and replace both secret values. Then run:

```text
docker compose up -d --build
```

The container listens on `127.0.0.1:8000` on the host. Put an HTTPS reverse proxy in front of it for Internet access. Do not publish the MCP port directly to the Internet.

Compose gives the container a 30-second stop grace period so an orderly shutdown can complete before Docker force-kills the process.

## OAuth and single sign-on (OIDC)

Optional. By default the MCP endpoint accepts only the static bearer token. MCP clients that
connect with OAuth (ChatGPT, Claude and other remote-MCP clients) need an authorization server;
set `OIDC_ISSUER` to turn one on. The server then signs people in through your identity provider
(for example authentik) and issues its own access tokens for `/mcp`.

Roles: the server is an **OIDC Relying Party** toward the identity provider (it never issues ID
tokens and exposes no JWKS) and the **OAuth authorization server + resource server** for `/mcp`.

When `OIDC_ISSUER` is unset or empty nothing changes: none of the routes below exist and `/mcp`
behaves exactly as before.

When it is set:

- The static bearer token keeps working next to OAuth access tokens, so existing clients are unaffected.
- `/mcp` without a valid token answers `401` with
  `WWW-Authenticate: Bearer resource_metadata="<public URL>/.well-known/oauth-protected-resource/mcp", scope="mcp"`
  (plus `error="invalid_token"` when a token was sent and rejected).
- Discovery: `/.well-known/oauth-protected-resource/mcp` (RFC 9728, also at `/.well-known/oauth-protected-resource`),
  `/.well-known/oauth-authorization-server` and `/.well-known/openid-configuration` (the same authorization-server
  metadata, for interoperability only).
- `/oauth/authorize`: CIMD client ids (the `client_id` is the HTTPS URL of the client's metadata document),
  S256 PKCE required. Sign-in is OIDC only: the browser goes straight to `/oidc/login` and the identity provider,
  comes back to `/oidc/callback`, and then sees a consent page (Approve / Deny).
- `/oauth/token`: `authorization_code` (PKCE) and `refresh_token` grants for public clients
  (`token_endpoint_auth_methods_supported: ["none"]`). Access tokens are HS256 JWTs signed with `JWT_SECRET`,
  `iss` = public URL, `aud` = `<public URL>/mcp`, valid for one hour; refresh tokens are opaque and valid for 30 days.

There are no local user accounts. The signed-in identity is the identity provider's issuer + `sub`
(carried in the access token as `idp` + `sub`), and **who may sign in is decided by the identity
provider** (in authentik: the application's policy bindings). Every person who can complete the
sign-in and approve the consent gets the same full access as the static bearer token. An
allow-list of subjects is out of scope.

### Environment

| Variable | Meaning |
|---|---|
| `OIDC_ISSUER` | Issuer URL exactly as the identity provider publishes it (authentik: `https://auth.example.org/application/o/<slug>/`, keep the trailing slash). Empty = feature off. |
| `OIDC_CLIENT_ID` | Required when `OIDC_ISSUER` is set. |
| `OIDC_CLIENT_SECRET` (or `OIDC_CLIENT_SECRET_FILE`) | Optional. Set = confidential client (`client_secret_basic`); unset = public client. PKCE is always used. |
| `OIDC_SCOPES` | Default `openid email profile`; must contain `openid`. |
| `OIDC_BUTTON_LABEL` | Label of the sign-in button on the error/retry pages. Default `Sign in with single sign-on`. |
| `PERSONAL_REPO_MCP_PUBLIC_URL` | Required when `OIDC_ISSUER` is set. The public `https://` origin of this server (no path), e.g. `https://mcp.example.com`. It is the OAuth issuer, the token audience is `<public URL>/mcp`, and the OIDC redirect URI is `<public URL>/oidc/callback`. An `https://` public URL is the production switch: `OIDC_ISSUER` must then be `https://` and the sign-in cookie is `Secure`. |
| `JWT_SECRET` (or `JWT_SECRET_FILE`) | Required when `OIDC_ISSUER` is set. Base64, at least 32 bytes: `openssl rand -base64 32`. Signs access tokens and consent tickets; changing it invalidates issued access tokens. |
| `PERSONAL_REPO_MCP_OAUTH_DB` | SQLite file for authorization codes, refresh tokens and pending sign-ins. Default: `data/oauth.sqlite` next to the repository root (`/srv/personal-repo-mcp/data/oauth.sqlite` in Docker). |

`OIDC_CREATE_USERS` and `OIDC_TRUST_EMAIL` (used by apps with local accounts) do not apply here:
this server has no user table. Invalid values of the variables above stop the server at startup
with a clear error. The identity provider does not need to be reachable at startup: discovery runs
on the first sign-in and is retried on the next one if it fails.

### Storage

Codes, refresh tokens and pending OIDC sign-ins (state, nonce, PKCE verifier, 10 minutes, single
use) are kept in a small SQLite database, not in the repository workspace. Codes, refresh tokens
and states are stored only as SHA-256 hashes. With Docker Compose the database lives in `./data`
on the host, mounted at `/srv/personal-repo-mcp/data`; create it writable for the container user:

```text
mkdir -p data
sudo chown 10001:10001 data
```

Losing the database only forces MCP clients to sign in again.

### Setting up authentik

1. **Applications → Providers → Create → OAuth2/OpenID Provider.** Client type *Confidential*,
   redirect URI `https://mcp.example.com/oidc/callback` (strict), and choose a **signing key** so ID
   tokens are RS256 (without one authentik signs with HS256, which this server does not accept).
   Keep the default `openid`, `email` and `profile` scope mappings.
2. **Applications → Applications → Create**, pick that provider, and bind the users or groups who may
   use the MCP server (policy / group bindings).
3. Copy the **OpenID Configuration Issuer** from the provider page into `OIDC_ISSUER`, and the client
   ID and secret into `OIDC_CLIENT_ID` / `OIDC_CLIENT_SECRET`.

Then, in `.env`:

```dotenv
PERSONAL_REPO_MCP_PUBLIC_URL=https://mcp.example.com
OIDC_ISSUER=https://auth.example.org/application/o/personal-repo-mcp/
OIDC_CLIENT_ID=...
OIDC_CLIENT_SECRET=...
JWT_SECRET=...   # openssl rand -base64 32
```

and restart with `docker compose up -d`. In the MCP client, add `https://mcp.example.com/mcp` as a
remote MCP server with OAuth; the client discovers everything else from the 401 challenge.

The consent page's `Content-Security-Policy` allows the client's redirect origin in `form-action`;
keep that if you add security headers at the reverse proxy, or approving will silently do nothing.

## Health

`GET /healthz` is unauthenticated and is intended for Docker/reverse-proxy health checks. MCP itself is mounted at `/mcp` and remains bearer-token protected (static token, or OAuth access token when OIDC is enabled).

## Persistence and backup

The `repositories/` host directory is the persistent workspace. It contains changes that may not yet have been pushed upstream, including untracked files. Back it up independently of GitHub. Recovery should restore the directory before starting the container.

## Security model

The security boundary is layered:

1. MCP bearer token (or, when OIDC is enabled, an OAuth access token obtained through single sign-on) authenticates the client.
2. `repositories.json` allow-lists repository IDs and their workspace locations.
3. Path containment prevents a repository workspace from escaping the configured root.
4. File operations reject writes into nested Git repositories when accessed through a parent repository.
5. Docker runs the application as an unprivileged user with `no-new-privileges` and all Linux capabilities dropped.
6. Host/Origin validation protects the Streamable HTTP endpoint against DNS-rebinding and unwanted browser origins.
7. Outbound MCP results scrub configured credentials before they reach the client.

The host should also protect the secret files, repository configuration, and persistent repository directory with normal filesystem permissions.

## Not included yet

This deployment intentionally does not introduce Docker orchestration, per-repository containers, a database server (the optional OAuth state is a local SQLite file), a remote artifact store, or automatic filesystem watching. Those can be added later without changing the single-container repository model.
