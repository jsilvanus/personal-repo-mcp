from __future__ import annotations

import argparse
import getpass
import json
import os
import tempfile
from pathlib import Path

DEFAULT_CONFIG = Path("/etc/personal-repo-mcp/repositories.json")
DEFAULT_PAT_FILE = Path("/etc/personal-repo-mcp/secrets/github-pat")


def _config(path: Path) -> dict:
    if not path.exists():
        return {"version": 1, "repositories": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Cannot read configuration: {path}: {exc}") from exc
    if isinstance(data, list):
        data = {"version": 1, "repositories": data}
    if not isinstance(data, dict) or data.get("version", 1) != 1 or not isinstance(data.get("repositories"), list):
        raise SystemExit("repositories.json must be a version 1 object with a repositories array")
    return {"version": 1, "repositories": data["repositories"]}


def _save(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent, text=True)
    try:
        os.fchmod(fd, 0o640)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass


def _selector(value: str) -> str:
    value = value.strip().removesuffix(".git")
    for prefix in ("https://github.com/", "http://github.com/"):
        if value.startswith(prefix):
            value = value[len(prefix):]
    value = value.strip("/")
    parts = value.split("/")
    if len(parts) != 2 or not all(parts) or any(part in {".", ".."} for part in parts) or "\\" in value:
        raise SystemExit("Repository selector must be OWNER/REPOSITORY, optionally using * or ?")
    return value


def _value(entry: dict) -> str:
    return str(entry.get("pattern", entry.get("id", "")))


def add_repo(args: argparse.Namespace) -> None:
    data = _config(args.config)
    selector = _selector(args.selector)
    entries = data["repositories"]
    if any(_value(item) == selector for item in entries if isinstance(item, dict)):
        print(f"Already allowed: {selector}")
        return
    if "*" in selector or "?" in selector:
        entries.append({"pattern": selector})
    else:
        owner, name = selector.split("/", 1)
        entries.append({
            "id": selector,
            "name": name,
            "remote": f"https://github.com/{owner}/{name}.git",
            "workspace": f"{owner}/{name}",
        })
    entries.sort(key=_value)
    _save(args.config, data)
    print(f"Allowed: {selector}")
    print("No repository was cloned or created.")


def remove_repo(args: argparse.Namespace) -> None:
    data = _config(args.config)
    selector = _selector(args.selector)
    old = len(data["repositories"])
    data["repositories"] = [item for item in data["repositories"] if _value(item) != selector]
    if len(data["repositories"]) == old:
        print(f"Not configured: {selector}")
        return
    _save(args.config, data)
    print(f"Removed from allow-list: {selector}")
    print("Existing workspace data was not deleted.")


def list_repo(args: argparse.Namespace) -> None:
    entries = _config(args.config)["repositories"]
    for item in entries:
        print(_value(item))
    if not entries:
        print("No repositories configured.")


def set_pat(args: argparse.Namespace) -> None:
    value = args.value if args.value is not None else getpass.getpass("GitHub PAT: ")
    if not value.strip():
        raise SystemExit("PAT cannot be empty")
    args.pat_file.parent.mkdir(parents=True, exist_ok=True)
    args.pat_file.write_text(value.strip() + "\n", encoding="utf-8")
    os.chmod(args.pat_file, 0o600)
    print(f"GitHub PAT stored in {args.pat_file}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mcp-config")
    parser.add_argument("--config", type=Path, default=Path(os.getenv("PERSONAL_REPO_MCP_CONFIG", DEFAULT_CONFIG)))
    parser.add_argument("--pat-file", type=Path, default=Path(os.getenv("PERSONAL_REPO_MCP_GITHUB_PAT_FILE", DEFAULT_PAT_FILE)))
    sub = parser.add_subparsers(dest="command", required=True)
    pat = sub.add_parser("pat", help="store the GitHub PAT")
    pat.add_argument("value", nargs="?", help="PAT; omit to prompt securely")
    pat.set_defaults(func=set_pat)
    add = sub.add_parser("add", help="modify the allow-list")
    add_repo_parser = add.add_subparsers(dest="kind", required=True).add_parser("repo", help="allow OWNER/REPOSITORY or OWNER/*")
    add_repo_parser.add_argument("selector")
    add_repo_parser.set_defaults(func=add_repo)
    remove = sub.add_parser("remove", help="remove an allow-list entry")
    remove_repo_parser = remove.add_subparsers(dest="kind", required=True).add_parser("repo")
    remove_repo_parser.add_argument("selector")
    remove_repo_parser.set_defaults(func=remove_repo)
    listing = sub.add_parser("list", help="list configuration")
    list_repo_parser = listing.add_subparsers(dest="kind", required=True).add_parser("repo")
    list_repo_parser.set_defaults(func=list_repo)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
