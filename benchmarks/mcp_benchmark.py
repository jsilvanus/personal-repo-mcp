#!/usr/bin/env python3
"""End-to-end Streamable HTTP benchmark for personal-repo-mcp.

Compares the configured Git backend with the hot-git backend through the
actual MCP/API surface. The benchmark assumes a running server and a small
benchmark repository configured on that server.

Usage:
  python3 benchmarks/mcp_benchmark.py --url http://127.0.0.1:8000/mcp \
      --repository benchmark --backend git

Run the same command with --backend hot-git for comparison.
"""
from __future__ import annotations

import argparse
import json
import statistics
import time
from dataclasses import dataclass

import httpx


@dataclass
class Stats:
    samples: list[float]

    @property
    def total(self) -> float:
        return sum(self.samples)

    @property
    def mean(self) -> float:
        return statistics.mean(self.samples)

    @property
    def median(self) -> float:
        return statistics.median(self.samples)

    @property
    def p95(self) -> float:
        if len(self.samples) < 2:
            return self.samples[0]
        return statistics.quantiles(self.samples, n=100, method="inclusive")[94]


def mcp_call(client: httpx.Client, url: str, request_id: int, tool: str, arguments: dict) -> tuple[float, dict]:
    payload = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "tools/call",
        "params": {"name": tool, "arguments": arguments},
    }
    started = time.perf_counter()
    response = client.post(url, json=payload)
    elapsed = time.perf_counter() - started
    response.raise_for_status()
    data = response.json()
    if "error" in data:
        raise RuntimeError(json.dumps(data["error"]))
    return elapsed, data


def benchmark_reads(client: httpx.Client, url: str, repository: str, path: str, count: int) -> Stats:
    samples = []
    for i in range(count):
        elapsed, _ = mcp_call(client, url, i + 1, "git_read_file", {"repository": repository, "path": path})
        samples.append(elapsed)
    return Stats(samples)


def benchmark_writes(client: httpx.Client, url: str, repository: str, path: str, count: int) -> Stats:
    samples = []
    for i in range(count):
        elapsed, _ = mcp_call(
            client,
            url,
            10_000 + i,
            "git_edit",
            {
                "repository": repository,
                "path": path,
                "content": f"mcp benchmark edit {i}\n",
                "message": f"mcp benchmark edit {i}",
            },
        )
        samples.append(elapsed)
    return Stats(samples)


def print_stats(name: str, stats: Stats) -> None:
    print(f"{name}")
    print(f"  samples: {len(stats.samples)}")
    print(f"  total:   {stats.total:.3f}s")
    print(f"  mean:    {stats.mean * 1000:.2f}ms")
    print(f"  median:  {stats.median * 1000:.2f}ms")
    print(f"  p95:     {stats.p95 * 1000:.2f}ms")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True, help="MCP Streamable HTTP endpoint")
    parser.add_argument("--repository", required=True)
    parser.add_argument("--backend", required=True, choices=("git", "hot-git"))
    parser.add_argument("--path", default="README.md")
    parser.add_argument("--reads", type=int, default=100)
    parser.add_argument("--writes", type=int, default=20)
    parser.add_argument("--warmup", type=int, default=5)
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args()

    if min(args.reads, args.writes, args.warmup) < 0:
        parser.error("counts must not be negative")

    headers = {"Accept": "application/json, text/event-stream"}
    with httpx.Client(timeout=args.timeout, headers=headers) as client:
        # Warm up the actual MCP path so connection/setup is not mixed into
        # steady-state operation measurements.
        for i in range(args.warmup):
            mcp_call(client, args.url, 100_000 + i, "git_read_file", {"repository": args.repository, "path": args.path})

        started = time.perf_counter()
        read_stats = benchmark_reads(client, args.url, args.repository, args.path, args.reads)
        read_wall = time.perf_counter() - started

        started = time.perf_counter()
        write_stats = benchmark_writes(client, args.url, args.repository, args.path, args.writes)
        write_wall = time.perf_counter() - started

    print(f"Backend: {args.backend}")
    print(f"URL: {args.url}")
    print(f"Repository: {args.repository}")
    print(f"Warmup: {args.warmup}")
    print("\nREAD — end-to-end MCP/API")
    print_stats("  requests", read_stats)
    print(f"  wall:     {read_wall:.3f}s")
    print("\nWRITE — end-to-end MCP/API")
    print_stats("  requests", write_stats)
    print(f"  wall:     {write_wall:.3f}s")
    print("\nRun this benchmark once with --backend git and once with --backend hot-git.")


if __name__ == "__main__":
    main()
