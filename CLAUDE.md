# CLAUDE.md

Guidance for Claude Code (or any agent) working in this repository.

## What this is

`personal-repo-mcp` is a self-hosted MCP server (Python, `mcp` SDK + Starlette/uvicorn,
streamable HTTP transport) that gives an AI agent a **persistent, multi-repository Git
workspace** on a VPS. The administrator controls which GitHub repositories may be
cloned (allow-list in `repositories.json`); the agent controls which allowed
repositories it actually clones, via MCP tools.

Core boundary: `RepositoryManager` (`src/personal_repo_mcp/repositories/manager.py`)
mediates every access to a repository workspace. Tools never touch `filesystem/` or
`git/` internals directly.

## Layout

```
src/personal_repo_mcp/
  main.py            Starlette app factory + entrypoint (personal-repo-mcp script)
  admin.py            mcp-config CLI (PAT/token setup, allow-list management)
  config.py           env/JSON settings loading + validation (Settings, load_settings)
  metrics.py          in-process metrics middleware
  mcp/
    server.py          create_mcp(): registers all tools/resources/prompts
    transport.py        BearerAuthMiddleware (constant-time token compare)
    prompts.py           MCP prompt registration (help-index prompt)
    errors.py
  tools/               MCP tool registrars, one module per surface area
    files.py git.py chain.py workspace.py
  repositories/        allow-list, workspace paths, RepositoryManager
  git/                 git command backend (runner.py = subprocess, no shell=True)
                       + backend.py: RepositoryBackend protocol, GitBackend (compat)
                       and HotGitBackend (treeless reads/edits via hot-git dep)
  filesystem/          file read/write/patch/search, path containment (paths.py)
  security/            policy.py + scopes.py (authorization model — see Known Issues),
                       secrets.py (output scrubbing of token/PAT)
  resources/           MCP resources: help text, repo/git/system state, subscriptions
  chain/               chain_command executor + model (single-repo op chaining)
  audit/               structured audit logging (metadata only, no file contents/secrets)
  operations/          long-running task/state tracking

tests/                 mirrors src/ layout (audit, chain, filesystem, git, mcp,
                       operations, repositories, resources, security, tools)
docs/                  DEPLOYMENT, SECURITY, PROTOCOL, TOOLS, PLAN, TECHNICAL_PLAN, etc.
benchmarks/            MCP + hot-git worker benchmarks
```

## Build, test, run

```bash
pip install -e ".[test]"          # installs mcp/starlette/uvicorn + hot-git (git dep) + pytest
python -m pytest -q               # 61 passed as of this writing
```

There is **no configured linter/formatter/type-checker** in this repo (no ruff, mypy,
black, or flake8 config in `pyproject.toml`). Match existing style by hand; don't add
tooling config unless asked.

To run the server locally you need `PERSONAL_REPO_MCP_TOKEN`,
`PERSONAL_REPO_MCP_GITHUB_PAT` (or their `_FILE` variants), and a repositories config
(`PERSONAL_REPO_MCP_CONFIG` pointing at JSON, or `PERSONAL_REPO_MCP_REPOSITORIES`
inline). See `docs/DEPLOYMENT.md` and `config/repositories.example.json`.

Docker: `docker compose up -d --build` after `mcp-config pat` / `mcp-config add repo`.

## History — server-startup and test-suite breakage (fixed)

The server and test suite were both broken as of commit `f9c84f8` and have since been
fixed on this branch. Kept here because the same class of bug (SDK version drift, and
import-path mistakes during refactors) is likely to recur:

- `mcp/server.py` imported `register_prompts` from `..tools.prompts`, which doesn't
  exist — prompt registration lives in `mcp/prompts.py`. Commit `094adec` moved three
  of four tool-registrar modules from `mcp/` to `tools/` and rewrote all four imports
  uniformly, missing that `prompts.py` never moved. This alone prevented the server
  from starting and the test suite from being collected.
- No `tests/` subdirectory had an `__init__.py`, and several test files shared a
  basename across subdirectories (`test_paths.py` in both `tests/filesystem/` and
  `tests/repositories/`; `test_files.py` in `tests/filesystem/` and `tests/tools/`;
  `test_git.py` in `tests/git/` and `tests/tools/`). Under pytest's default
  rootdir-relative import mode this caused `import file mismatch` collection errors.
  Fixed by adding `__init__.py` to every `tests/` subpackage.
- `mcp/server.py` imported `Context` from `mcp.server.context` instead of
  `mcp.server.mcpserver` (the class the `@mcp.tool()`/`@mcp.resource()` decorators
  actually special-case for injection and exclude from JSON-schema generation). Every
  other file in the codebase already used the correct import — this was the one
  straggler, and it broke `tools/list` schema generation for `clone_repository`. The
  earlier commits `9944942`/`d82962f`/`2178958`/`80320ef` ("fix: import MCP context
  from sdk context module" etc.) were chasing the same class of bug elsewhere. **If a
  `Context`-typed tool/resource parameter starts throwing `PydanticInvalidForJsonSchema`
  or a "Context injection ... not supported" `ValueError` after bumping the `mcp`
  dependency, check this import first** — the pinned range (`mcp>=2.0,<3`) allows the
  SDK's internal module layout to shift under you.
- `resources/help.py` registered static (non-templated) `mcp://help/*` resources with
  a handler built as `lambda text=text: text` — a default-argument trick to dodge
  Python's loop late-binding bug. The installed SDK version now rejects *any*
  parameter (defaulted or not) on a static resource. Fixed with a real closure
  factory (`_make_help_handler`) instead of a default-arg lambda.
- `resources/system.py`'s three static resources (`system_info`, `system_storage`,
  `system_repositories`) each declared an unused `ctx: Context` parameter. The SDK
  now explicitly disallows Context injection on non-templated resources. Removed the
  parameter (it was dead code) rather than working around it.
- A handful of tests had drifted from the code they exercised: `Settings(...)`
  call-sites missing the `github_pat`/`git_backend`/`repository_patterns` fields added
  later; `register_resources(...)` missing the `metrics` argument; a
  `RepositoryManager(...)` call passing the wrong positional args; an assertion
  expecting a tool named `read_file_tool` instead of its actual registered name,
  `read_file`; a prompt test asserting on the raw `GetPromptResult` object instead of
  `.messages`, and checking `isinstance(content, dict)` instead of the real
  `EmbeddedResource`/`TextContent` SDK types; and `tests/git/test_hot_git_backend.py`
  relying on `git init`'s default branch being `main`, which isn't true on every
  system (this one defaults to `master`) — fixed with `git init -b main`.

All of the above is fixed; `python -m pytest -q` passes clean (61 passed). Re-verify
after any `mcp` or `hot-git` dependency bump, since several of these were pure SDK
version drift, not one-off typos.

## Security model — what's real vs. what's not wired up

- Path traversal containment, bearer-token auth (`hmac.compare_digest`), PAT handling
  via `GIT_ASKPASS` (never on argv/process list), and secret scrubbing of MCP output
  are implemented and match `docs/SECURITY.md`.
- `security/policy.py` and `security/scopes.py` define a `Policy`/`Scope` model
  (`destructive`, `shell`, per-operation `check()`, `scope_from_token()`) that is
  **never called** from `mcp/server.py` or any `tools/*.py` — grep confirms zero
  callers of `scope_from_token`. Every valid bearer token currently gets full,
  unscoped access to every tool. Don't treat this module as enforcing anything; it's
  scaffolding for the "token scopes" item `docs/SECURITY.md` lists under future work.
  If you wire it up, add an integration test that exercises it against real tool
  dispatch (only `test_policy.py` exists today, tested in isolation).

## Conventions worth following

- Tools are registered via `register_*_tools(mcp, repositories)` factories, closed
  over a `RepositoryManager`. Add new tools by extending an existing registrar or
  adding a new one in `tools/`, then wiring it into `mcp/server.py`'s `create_mcp()`.
- `git/runner.py` never uses `shell=True` — always pass argv lists. Preserve this.
- Git backends are chosen per-repository via `RepositoryManager` behind the
  `RepositoryBackend` protocol (`git/backend.py`): `GitBackend` (default, command-line
  compat) and `HotGitBackend` (treeless, opt-in via
  `PERSONAL_REPO_MCP_GIT_BACKEND=hot-git`). Only `git_read_file`/`git_edit` are
  integrated with hot-git so far; everything needing a working tree or git's
  merge/rebase machinery stays on `GitBackend`. Keep that split when adding backend
  operations rather than collapsing it prematurely.
- Config loading (`config.py`) validates aggressively at startup (repo ids, workspace
  containment under root, port range, JSON schema version) — extend `load_settings`
  in the same fail-fast style rather than deferring validation into request handlers.
