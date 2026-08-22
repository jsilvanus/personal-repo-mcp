# Post-MVP Plan: Restricted SSH Git Access

## Status

**Planned, post-MVP.** This document defines a small SSH transport for the Git repositories managed by `personal-repo-mcp`.

The goal is to make an MCP-managed repository usable as a normal Git remote from a PC or another development machine without exposing a general-purpose SSH shell.

## Goal

Allow standard Git clients to perform operations such as:

```text
git clone
 git fetch
git pull
git push
```

against repositories managed by the MCP server.

The intended topology is:

```text
PC
 │
 │ Git over SSH
 ▼
MCP VPS
 │
 │ Git over SSH / GitHub remote
 ▼
GitHub
```

The SSH interface is an additional transport. MCP remains the management/agent protocol.

## Core design

Run a small SSH server in the same Docker deployment as the MCP initially. The SSH server must be restricted to Git's standard server-side commands:

```text
git-upload-pack   -> clone/fetch
 git-receive-pack -> push
```

It must not provide an interactive shell or arbitrary command execution.

The server should invoke the system Git executable with argument-safe process execution. Do not implement the Git wire protocol ourselves.

## Authentication model

SSH authentication and MCP authentication are separate concerns.

### Client authentication

The SSH server authenticates clients using SSH public keys. The client keeps the corresponding private key.

For example, a user's existing personal key can be authorized for:

```text
VPS login
MCP Git SSH
(optional) GitHub SSH access
```

The private key must **never** be copied into the Docker container merely to enable Git access.

The container needs the SSH server's host key and the authorized client public keys, not the client's private key.

### Host identity

The SSH server needs a persistent host key so recreating the Docker container does not unexpectedly change the server identity.

The host key should live in persistent external configuration/storage, not only in the container filesystem.

### MCP credentials

The MCP API credential remains separate from SSH authentication.

### GitHub credentials

The MCP's GitHub PAT remains separate from SSH client authentication. A future user may also authorize their personal SSH key directly with GitHub, but this is optional and outside the SSH server's authentication mechanism.

The credential model is therefore:

```text
PC private SSH key
        │
        ├── VPS SSH
        └── MCP Git SSH

MCP API credential
        │
        └── MCP protocol

GitHub PAT
        │
        └── MCP -> GitHub
```

## Repository authorization

The SSH service must use the same repository authorization boundary as the MCP wherever practical.

A Git SSH request must resolve to a repository that is explicitly allowed by the external repository configuration.

A client must not be able to turn a repository argument into arbitrary filesystem access such as:

```text
../../etc
/home/other-user
/config/secrets
```

Repository names should be logical identifiers mapped to configured repository paths. The SSH layer should never accept an arbitrary filesystem path as an authorization decision.

The same allow-list that controls which repositories the MCP may operate on should be the basis for Git SSH access, with an explicit configuration option if SSH access should be more restrictive than MCP access.

## SSH account and command restrictions

Use a dedicated restricted Git account/identity for the service.

The account must not have:

- interactive shell access;
- arbitrary command execution;
- unrestricted filesystem access;
- access to Docker internals;
- access to MCP configuration secrets.

The SSH authentication layer should force Git server commands or equivalent restricted command handling.

The accepted operation should be limited to the Git transport commands needed by the service.

## Repository path mapping

Prefer a logical form such as:

```text
git clone mcp@server:foo
```

where `foo` is resolved by the server to the configured repository.

Do not require clients to know the Docker-internal filesystem path.

A repository may be represented internally as:

```text
foo -> /data/repositories/foo
```

The exact mapping should be shared with the MCP repository manager rather than duplicated in the SSH service.

## Docker deployment

Initially use the existing single-container deployment model rather than introducing orchestration solely for SSH.

Expose a configurable SSH port, normally a non-conflicting host port mapped to the container's SSH listener.

Persist:

```text
SSH host key
authorized public keys
SSH configuration
repository configuration
```

outside the container where appropriate.

The SSH listener should bind only to the intended interface(s), according to deployment configuration.

## Configuration

Extend `mcp-config` rather than requiring manual editing of container internals.

Provisional commands:

```text
mcp-config ssh enable
mcp-config ssh disable
mcp-config ssh status
mcp-config ssh add-key <public-key>
mcp-config ssh remove-key <key-id>
mcp-config ssh list-keys
mcp-config ssh port <port>
```

Exact CLI syntax is provisional.

The configuration should support:

```text
ssh.enabled
ssh.port
ssh.host_key_path
ssh.authorized_keys_path
ssh.allowed_repositories
```

The repository allow-list remains the primary authorization layer; `allowed_repositories` can optionally narrow SSH access further.

## Git workflow

A typical workflow should be:

```text
1. mcp-config add repo foo
2. MCP/server makes foo available
3. PC: git clone mcp@server:foo
4. PC: edit files
5. PC: git commit
6. PC: git push
7. MCP agents can observe the updated repository
8. MCP or PC can push/pull against GitHub as configured
```

Multiple Git remotes remain a normal Git concern:

```text
PC
├── mcp -> VPS MCP repository
└── github -> GitHub repository
```

The MCP repository can similarly have a GitHub remote.

## Interaction with the existing PAT

The GitHub PAT is not used to authenticate the PC to the MCP SSH server.

It remains the credential used when the MCP/server itself communicates with GitHub over HTTPS, unless a future configuration explicitly supports a different GitHub transport.

Do not copy the GitHub PAT into SSH configuration.

## Relationship to future treeless workers

The SSH transport should expose ordinary Git refs and commits. It must not make assumptions about whether a ref was produced by a working tree or by a future treeless worker.

This allows the future architecture to look like:

```text
Git repository
├── main
├── feature/foo
├── worker/agent-1
└── worker/agent-2
```

The SSH service simply serves the Git repository.

A future treeless worker implementation can create commits and refs, and a normal Git client can fetch those refs over SSH.

The worker namespace must therefore remain a Git concern rather than an SSH-specific concept.

## Security hardening

Before production use, test at least:

- unauthorized SSH key is rejected;
- authorized key can clone an allowed repository;
- authorized key cannot clone an unallowed repository;
- repository traversal attempts are rejected;
- shell attempts are rejected;
- arbitrary command execution is rejected;
- malformed Git command arguments are rejected;
- a repository outside the configured root cannot be reached;
- SSH host key persists across container recreation;
- revoked keys stop working;
- Git push cannot write outside the repository object database;
- secrets are not exposed through SSH errors or Git command output;
- concurrent MCP and SSH Git operations behave correctly.

SSH connection and Git operation logs should identify the authorized key/user and logical repository, without logging private keys, tokens, or other secrets.

## Resource and deployment limits

The SSH service runs in the same Docker resource boundary as the MCP initially. CPU and storage limits therefore apply to the combined service.

The SSH server must not introduce a second uncontrolled data path around the repository storage limits already planned for the deployment.

Git operations such as clone, fetch, and push can consume significant CPU, memory, temporary disk space, and network bandwidth. These should be considered when hardening Docker limits.

## Implementation architecture

Prefer clear separation:

```text
SSH transport
    │
    ▼
SSH authentication / command restriction
    │
    ▼
Repository resolver
    │
    ▼
Git upload-pack / receive-pack
    │
    ▼
Existing repository
```

The repository resolver should be shared with the MCP rather than reimplementing repository authorization.

The SSH transport itself should remain small and replaceable. If a mature Python SSH server library can provide the required restrictions safely, use it rather than implementing SSH cryptography/protocol handling ourselves.

## Testing strategy

Add integration tests using a real temporary Git repository and an actual SSH client where practical.

Test:

1. clone through SSH;
2. fetch through SSH;
3. push through SSH;
4. invalid key;
5. invalid repository;
6. path traversal;
7. shell/command injection attempts;
8. key revocation;
9. host-key persistence;
10. concurrent MCP and SSH access;
11. large repository transfer;
12. submodule repositories and gitlinks;
13. secret scrubbing in SSH/MCP-visible errors.

## Implementation order

1. Define the SSH configuration schema and repository mapping.
2. Define the security boundary and restricted Git command model.
3. Select and evaluate a Python SSH server library.
4. Implement persistent host-key handling.
5. Implement authorized public-key authentication.
6. Implement logical repository resolution through the existing allow-list.
7. Implement restricted `git-upload-pack` and `git-receive-pack` execution.
8. Add `mcp-config` SSH management commands.
9. Integrate into the existing single-Docker deployment.
10. Add clone/fetch/push integration tests.
11. Add security and traversal tests.
12. Document PC setup and GitHub multi-remote workflows.
13. Validate interaction with future treeless worker refs.

## Explicit non-goals

- no general-purpose SSH shell;
- no remote command execution;
- no SCP/SFTP service initially;
- no custom Git wire protocol;
- no GitHub account management;
- no requirement that the MCP container hold user private SSH keys;
- no separate Docker orchestration layer;
- no automatic synchronization between PC, VPS, and GitHub;
- no automatic merge/rebase of concurrent branches.

## MVP boundary

This is a **post-MVP deployment/transport feature**. The existing MCP protocol and repository management remain fully usable without SSH.

The feature is intentionally designed now because exposing standard Git access affects repository layout, Docker networking, configuration, authorization, and future treeless-worker refs. Implementing it later should not require redesigning those foundations.
