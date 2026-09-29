# Security

Personal Repo MCP is intended to run on a private VPS while granting an AI agent write access to persistent Git workspaces. The server therefore treats repository isolation and destructive-operation control as security boundaries.

## Current controls

- HTTPS is expected at deployment time.
- The MCP endpoint requires a bearer token: the static token, or (when `OIDC_ISSUER` is set) an OAuth access token.
- Static-token authentication is constant-time compared.
- OAuth (optional): the server is an OIDC relying party (state bound to an httpOnly cookie, nonce, PKCE, ID token verified against the IdP's JWKS with asymmetric algorithms only) and an OAuth authorization server for `/mcp` (CIMD client ids with SSRF limits, S256 PKCE, single-use 60-second codes, HS256 access tokens bound to `iss` and `aud`). Codes, refresh tokens and sign-in states are stored hashed; tokens, codes and ID tokens are never logged. Who may sign in is decided by the identity provider's application policy; every signed-in, consenting user gets full access (no per-user scopes yet).
- MCP transport security keeps DNS-rebinding protection enabled.
- Repository paths are resolved and contained below the configured repository root.
- File operations do not intentionally expose arbitrary filesystem paths.
- Git execution does not use a shell.
- Arbitrary shell execution is not part of the API.
- Force push, force branch deletion and hard reset are not enabled by the Phase 3 core API.
- `chain_command` is restricted to one repository and cannot invoke itself or repository-management tools.
- Audit events record operation metadata but not file contents or credentials.

## Threats requiring care

Git hooks, submodules, repository remotes and build/test execution can turn repository write access into arbitrary code execution on the VPS. This is an explicit trust boundary for the personal deployment and should be isolated further before the service is exposed to less-trusted agents.

Future work should include token scopes, per-repository authorization, stronger destructive-operation confirmation, and sandboxing for code execution.
