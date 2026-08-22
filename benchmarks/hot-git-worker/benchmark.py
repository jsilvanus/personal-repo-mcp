#!/usr/bin/env python3
"""Benchmark per-request Git object access against a persistent cat-file worker."""

from __future__ import annotations

import argparse
import os
import random
import shutil
import subprocess
import tempfile
import time
from pathlib import Path


def run(*args: str, cwd: Path) -> str:
    result = subprocess.run(
        args,
        cwd=cwd,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return result.stdout


def git(*args: str, cwd: Path) -> str:
    return run("git", *args, cwd=cwd)


def make_repo(files: int) -> tuple[Path, list[str]]:
    root = Path(tempfile.mkdtemp(prefix="hot-git-worker-"))
    try:
        git("init", "-q", cwd=root)
        git("config", "user.name", "benchmark", cwd=root)
        git("config", "user.email", "benchmark@example.invalid", cwd=root)

        objects: list[str] = []
        for i in range(files):
            path = root / f"file-{i:06d}.txt"
            path.write_text(
                f"benchmark file {i}\n" + ("payload " * 20) + "\n",
                encoding="utf-8",
            )

        git("add", ".", cwd=root)
        git("commit", "-q", "-m", "benchmark", cwd=root)

        # Resolve blob IDs once. The benchmark then measures object access,
        # not path/tree traversal.
        output = git("ls-tree", "-r", "HEAD", cwd=root)
        for line in output.splitlines():
            parts = line.split()
            if len(parts) >= 3 and parts[1] == "blob":
                objects.append(parts[2])

        if not objects:
            raise RuntimeError("repository contains no blob objects")
        return root, objects
    except Exception:
        shutil.rmtree(root, ignore_errors=True)
        raise


def read_one_process(repo: Path, object_id: str) -> bytes:
    result = subprocess.run(
        ["git", "cat-file", "blob", object_id],
        cwd=repo,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout


def benchmark_cold(repo: Path, objects: list[str]) -> tuple[float, int]:
    started = time.perf_counter()
    total = 0
    for object_id in objects:
        total += len(read_one_process(repo, object_id))
    return time.perf_counter() - started, total


class CatFileWorker:
    """Long-lived git cat-file --batch process."""

    def __init__(self, repo: Path) -> None:
        self.process = subprocess.Popen(
            ["git", "cat-file", "--batch"],
            cwd=repo,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        assert self.process.stdin is not None
        assert self.process.stdout is not None
        self.stdin = self.process.stdin
        self.stdout = self.process.stdout

    def read(self, object_id: str) -> bytes:
        self.stdin.write((object_id + "\n").encode("ascii"))
        self.stdin.flush()

        header = self.stdout.readline()
        if not header:
            raise RuntimeError("git cat-file worker exited unexpectedly")
        parts = header.split()
        if len(parts) < 3 or parts[1] == b"missing":
            raise RuntimeError(f"unexpected cat-file response: {header!r}")

        size = int(parts[2])
        data = self.stdout.read(size)
        newline = self.stdout.read(1)
        if len(data) != size or newline != b"\n":
            raise RuntimeError("truncated cat-file response")
        return data

    def close(self) -> None:
        if self.process.stdin:
            self.process.stdin.close()
        returncode = self.process.wait(timeout=5)
        if returncode != 0:
            stderr = self.process.stderr.read() if self.process.stderr else b""
            raise RuntimeError(f"cat-file exited with {returncode}: {stderr!r}")


def benchmark_hot(repo: Path, objects: list[str], repeat: int) -> tuple[float, int]:
    worker = CatFileWorker(repo)
    try:
        started = time.perf_counter()
        total = 0
        for object_id in objects:
            total += len(worker.read(object_id))
        elapsed = time.perf_counter() - started

        # Repeat a smaller working set to show the best-case effect of keeping
        # the Git process alive. This is still Git/OS caching, not an app cache.
        if repeat:
            sample = objects[: min(repeat, len(objects))]
            for object_id in sample:
                total += len(worker.read(object_id))
        return elapsed, total
    finally:
        worker.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--files", type=int, default=1000)
    parser.add_argument("--reads", type=int, default=500)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    if args.files < 1 or args.reads < 1:
        parser.error("--files and --reads must be positive")

    random.seed(args.seed)
    repo, objects = make_repo(args.files)
    try:
        # Use a random sample so the measured reads are not merely sequential.
        reads = [random.choice(objects) for _ in range(args.reads)]

        setup_started = time.perf_counter()
        git("gc", "--quiet", cwd=repo)
        setup_elapsed = time.perf_counter() - setup_started

        print(f"Repository: {repo}")
        print(f"Files/blobs: {len(objects):,}")
        print(f"Reads: {len(reads):,}")
        print(f"Pack/GC setup: {setup_elapsed:.3f}s")
        print()

        cold_time, cold_bytes = benchmark_cold(repo, reads)
        hot_time, hot_bytes = benchmark_hot(repo, reads, repeat=min(100, len(reads)))

        print("One Git process per object")
        print(f"  time:  {cold_time:.3f}s")
        print(f"  bytes: {cold_bytes:,}")
        print()
        print("Persistent git cat-file --batch")
        print(f"  time:  {hot_time:.3f}s")
        print(f"  bytes: {hot_bytes:,} (includes repeat sample)")
        print()

        if hot_time > 0:
            print(f"Cold / persistent ratio: {cold_time / hot_time:.2f}x")
        print()
        print("Note: this is an object-access microbenchmark, not an MCP benchmark.")
    finally:
        shutil.rmtree(repo, ignore_errors=True)


if __name__ == "__main__":
    main()
