#!/usr/bin/env python3
"""Manage the personal-repo-mcp repository allow-list.

This is an administrative tool. It edits repositories.json; it is deliberately
not exposed through the MCP server.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

DEFAULT_CONFIG = Path("/etc/personal-repo-mcp/repositories.json")
DEFAULT_ROOT = Path("/srv/personal-repo-mcp/repositories")


def load_config(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"version": 1, "repositories": []}
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Cannot read {path}: {exc}") from exc

    if isinstance(raw, list):
        raw = {"version": 1, "repositories": raw}
    if not isinstance(raw, dict) or raw.get("version", 1) != 1:
        raise SystemExit(f"Unsupported configuration format in {path}")

    repositories = raw.get("repositories")
    if not isinstance(repositories, list):
        raise SystemExit("Configuration must contain a repositories array")

    return {"version": 1, "repositories": repositories}


def validate_id(repo_id: str) -> None:
    if not repo_id or "/" in repo_id or "\\" in repo_id or repo_id in {".", ".."}:
        raise SystemExit(f"Invalid repository id: {repo_id!r}")


def write_config(path: Path, config: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Atomic replacement prevents a failed write from leaving a half-written
    # allow-list. Keep restrictive permissions for a file outside the repo.
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(config, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp_name, 0o640)
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def cmd_list(config: dict[str, Any]) -> int:
    repositories = config["repositories"]
    if not repositories:
        print("No repositories configured.")
        return 0
    for repo in repositories:
        print(f"{repo['id']}\t{repo['name']}\t{repo['workspace']}\t{repo['remote']}")
    return 0


def cmd_add(config: dict[str, Any], args: argparse.Namespace, root: Path) -> int:
    validate_id(args.id)
    repositories = config["repositories"]
    if any(repo.get("id") == args.id for repo in repositories):
        raise SystemExit(f"Repository id already exists: {args.id}")

    workspace = Path(args.workspace) if args.workspace else root / args.id
    if not workspace.is_absolute():
        workspace = root / workspace
    workspace = workspace.resolve()
    root = root.resolve()
    if workspace == root or root not in workspace.parents:
        raise SystemExit(f"Workspace must be below repository root: {workspace}")

    repositories.append(
        {
            "id": args.id,
            "name": args.name or args.id,
            "remote": args.remote,
            "workspace": str(workspace),
        }
    )
    repositories.sort(key=lambda repo: repo["id"])
    return 0


def cmd_remove(config: dict[str, Any], args: argparse.Namespace) -> int:
    repositories = config["repositories"]
    matches = [repo for repo in repositories if repo.get("id") == args.id]
    if not matches:
        raise SystemExit(f"Repository id not found: {args.id}")
    if not args.yes:
        answer = input(f"Remove {args.id} from the allow-list? [y/N] ").strip().lower()
        if answer not in {"y", "yes"}:
            print("Cancelled.")
            return 0
    config["repositories"] = [repo for repo in repositories if repo.get("id") != args.id]
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage personal-repo-mcp repositories.json")
    parser.add_argument("--config", type=Path, default=Path(os.getenv("PERSONAL_REPO_MCP_CONFIG", DEFAULT_CONFIG)))
    parser.add_argument("--root", type=Path, default=Path(os.getenv("PERSONAL_REPO_MCP_ROOT", DEFAULT_ROOT)))
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="List configured repositories")

    add = sub.add_parser("add", help="Add a repository to the allow-list")
    add.add_argument("id")
    add.add_argument("remote")
    add.add_argument("--name")
    add.add_argument("--workspace")

    remove = sub.add_parser("remove", help="Remove a repository from the allow-list")
    remove.add_argument("id")
    remove.add_argument("--yes", action="store_true", help="Do not ask for confirmation")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    config = load_config(args.config)

    if args.command == "list":
        return cmd_list(config)
    if args.command == "add":
        result = cmd_add(config, args, args.root)
    else:
        result = cmd_remove(config, args)

    write_config(args.config, config)
    print(f"Updated {args.config}")
    return result


if __name__ == "__main__":
    sys.exit(main())
