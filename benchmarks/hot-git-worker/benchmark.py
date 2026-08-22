#!/usr/bin/env python3
"""Benchmark persistent Git object access and treeless workflows."""
from __future__ import annotations

import argparse
import concurrent.futures
import os
import random
import shutil
import subprocess
import tempfile
import time
from pathlib import Path


def run(args: list[str], cwd: Path, *, input: bytes | None = None, env=None) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=cwd, input=input, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, env=env)


def git(*args: str, cwd: Path, input: bytes | None = None, env=None) -> bytes:
    return run(["git", *args], cwd, input=input, env=env).stdout


def make_repo(files: int) -> tuple[Path, str, list[str]]:
    root = Path(tempfile.mkdtemp(prefix="hot-git-worker-"))
    try:
        run(["git", "init", "-q"], root)
        git("config", "user.name", "benchmark", cwd=root)
        git("config", "user.email", "benchmark@example.invalid", cwd=root)
        for i in range(files):
            path = root / f"d{i % 20}" / f"f{i}.txt"
            path.parent.mkdir(exist_ok=True)
            path.write_text(f"file {i}\n" + ("payload " * 20) + "\n", encoding="utf-8")
        git("add", ".", cwd=root)
        git("commit", "-qm", "benchmark", cwd=root)
        head = git("rev-parse", "HEAD", cwd=root).decode().strip()
        tree = git("ls-tree", "-r", "--name-only", "HEAD", cwd=root).decode().splitlines()
        return root, head, tree
    except Exception:
        shutil.rmtree(root, ignore_errors=True)
        raise


class Batch:
    """Persistent git cat-file --batch connection."""
    def __init__(self, repo: Path):
        self.p = subprocess.Popen(["git", "cat-file", "--batch"], cwd=repo,
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        assert self.p.stdin and self.p.stdout

    def read(self, oid: str) -> bytes:
        self.p.stdin.write((oid + "\n").encode()); self.p.stdin.flush()
        header = self.p.stdout.readline(); parts = header.split()
        if len(parts) < 3 or parts[1] == b"missing": raise RuntimeError(header)
        size = int(parts[2]); data = self.p.stdout.read(size); self.p.stdout.read(1)
        return data

    def close(self):
        self.p.stdin.close(); self.p.wait(timeout=5)


def parse_tree(data: bytes) -> dict[str, tuple[str, str]]:
    result = {}; i = 0
    while i < len(data):
        sp = data.index(b" ", i); nul = data.index(b"\0", sp)
        name = data[sp + 1:nul].decode(); oid = data[nul + 1:nul + 21].hex()
        result[name] = (data[i:sp].decode(), oid); i = nul + 21
    return result


def make_tree_reader(repo: Path, head: str):
    root = git("rev-parse", f"{head}^{{tree}}", cwd=repo).decode().strip()
    worker = Batch(repo); trees: dict[str, dict[str, tuple[str, str]]] = {}

    def find(path: str) -> str:
        oid = root
        for part in path.split("/"):
            if oid not in trees: trees[oid] = parse_tree(worker.read(oid))
            oid = trees[oid][part][1]
        return oid
    return worker, find


def cold_reads(repo: Path, head: str, paths: list[str]) -> tuple[float, int]:
    start = time.perf_counter(); total = 0
    for path in paths:
        total += len(run(["git", "show", f"{head}:{path}"], repo).stdout)
    return time.perf_counter() - start, total


def hot_reads(repo: Path, head: str, paths: list[str]) -> tuple[float, int]:
    worker, find = make_tree_reader(repo, head); start = time.perf_counter(); total = 0
    try:
        for path in paths: total += len(worker.read(find(path)))
    finally: worker.close()
    return time.perf_counter() - start, total


def treeless_edit(repo: Path, head: str, paths: list[str]) -> tuple[float, str]:
    index = Path(tempfile.mktemp(prefix="hot-git-index-")); env = os.environ.copy(); env["GIT_INDEX_FILE"] = str(index)
    try:
        run(["git", "read-tree", head], repo, env=env); start = time.perf_counter()
        for path in paths:
            old = run(["git", "show", f"{head}:{path}"], repo).stdout
            new = old + b"\n# treeless edit\n"
            blob = git("hash-object", "-w", "--stdin", cwd=repo, input=new).decode().strip()
            run(["git", "update-index", "--add", "--cacheinfo", "100644", blob, path], repo, env=env)
        tree = git("write-tree", cwd=repo, env=env).decode().strip()
        commit = git("commit-tree", tree, "-p", head, "-m", "benchmark treeless edit", cwd=repo, env=env).decode().strip()
        return time.perf_counter() - start, commit
    finally:
        index.unlink(missing_ok=True)


def cas_test(repo: Path, head: str) -> tuple[int, int]:
    a = treeless_edit(repo, head, ["d1/f1.txt"])[1]; b = treeless_edit(repo, head, ["d2/f2.txt"])[1]
    ref = "refs/bench/cas"; git("update-ref", ref, head, cwd=repo)
    r1 = subprocess.run(["git", "update-ref", ref, a, head], cwd=repo).returncode
    r2 = subprocess.run(["git", "update-ref", ref, b, head], cwd=repo).returncode
    subprocess.run(["git", "update-ref", "-d", ref], cwd=repo, check=True)
    return r1, r2


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--files", type=int, default=1000); ap.add_argument("--reads", type=int, default=500); ap.add_argument("--edit-files", type=int, default=10); ap.add_argument("--workers", type=int, default=8); ap.add_argument("--seed", type=int, default=42); a = ap.parse_args()
    random.seed(a.seed); repo, head, paths = make_repo(a.files)
    try:
        reads = [random.choice(paths) for _ in range(a.reads)]; edits = paths[:a.edit_files]; git("gc", "--quiet", cwd=repo)
        cold, cb = cold_reads(repo, head, reads); hot, hb = hot_reads(repo, head, reads)
        edit, commit = treeless_edit(repo, head, edits); cas = cas_test(repo, head)
        chunks = [reads[i::a.workers] for i in range(a.workers)]; start = time.perf_counter()
        with concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as pool: times = list(pool.map(lambda c: hot_reads(repo, head, c)[0], chunks))
        concurrent_time = time.perf_counter() - start
        print(f"files={a.files} reads={a.reads} edits={a.edit_files} workers={a.workers}")
        print(f"cold read_file:       {cold:.3f}s ({cb:,} bytes)")
        print(f"hot object worker:    {hot:.3f}s ({hb:,} bytes), speedup={cold / hot:.2f}x")
        print(f"treeless edit+commit: {edit:.3f}s ({commit[:12]})")
        print(f"CAS competing refs:   {cas} (expected one 0, one non-zero)")
        print(f"{a.workers} concurrent workers: {concurrent_time:.3f}s (sum={sum(times):.3f}s)")
    finally:
        shutil.rmtree(repo, ignore_errors=True)


if __name__ == "__main__": main()
