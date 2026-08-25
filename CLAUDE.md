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
python -m pytest -q               # test suite — see "Known issue" below, currently broken
```

There is **no configured linter/formatter/type-checker** in this repo (no ruff, mypy,
black, or flake8 config in `pyproject.toml`). Match existing style by hand; don't add
tooling config unless asked.

To run the server locally you need `PERSONAL_REPO_MCP_TOKEN`,
`PERSONAL_REPO_MCP_GITHUB_PAT` (or their `_FILE` variants), and a repositories config
(`PERSONAL_REPO_MCP_CONFIG` pointing at JSON, or `PERSONAL_REPO_MCP_REPOSITORIES`
inline). See `docs/DEPLOYMENT.md` and `config/repositories.example.json`.

Docker: `docker compose up -d --build` after `mcp-config pat` / `mcp-config add repo`.

## Known issue — broken import (fix before anything else touches `mcp/server.py`)

`src/personal_repo_mcp/mcp/server.py` imports:

```python
from ..tools.prompts import register_prompts
```

but prompt registration actually lives at `src/personal_repo_mcp/mcp/prompts.py` —
`tools/prompts.py` does not exist. This was introduced by commit `094adec` ("fix:
import tool registrars from tools package"), which moved the other three tool
registrars from `mcp/` to `tools/` but not `prompts.py`, then rewrote all four
imports uniformly. **The server cannot start and the test suite cannot even be
collected** in this state — confirmed by installing dependencies into a clean venv
and running `pytest`. Fix is a one-line import correction (`from ..prompts import
register_prompts`, since `prompts.py` stays in `mcp/`).

There is also a **separate, pre-existing test-collection problem**: several test
files share a basename across different `tests/` subdirectories (`test_paths.py` in
both `tests/filesystem/` and `tests/repositories/`; `test_files.py` in
`tests/filesystem/` and `tests/tools/`; `test_git.py` in `tests/git/` and
`tests/tools/`), and no `tests/` subdirectory has an `__init__.py`. Under pytest's
default rootdir-relative import mode this causes `import file mismatch` errors during
collection, independent of the import bug above. Fix by adding `__init__.py` to every
`tests/` subpackage (or renaming the duplicated files) — do this before trusting any
"tests pass" result in this repo, since collection currently aborts before any test
runs.

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
