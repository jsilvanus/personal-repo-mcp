# Hot Git Worker Benchmark

This benchmark tests the hypothesis behind a future treeless Git worker:

> Keeping a Git object process alive and using `git cat-file --batch` can be substantially faster than spawning a new Git process for every object read.

It deliberately does **not** implement the future MCP worker. It is a small, isolated experiment that compares two access patterns against the same Git repository:

1. **cold subprocess** — spawn `git cat-file --batch` for each object;
2. **persistent worker** — keep one `git cat-file --batch` process alive and send many object requests through it.

The benchmark also reports a repeated-read case, which gives the future in-process LRU cache experiment a baseline.

## Requirements

- Python 3.11+
- Git available as `git` on `PATH`

No project dependencies are required.

## Run

From the repository root:

```bash
python benchmarks/hot-git-worker/benchmark.py
```

Optional parameters:

```bash
python benchmarks/hot-git-worker/benchmark.py --files 10000 --reads 5000
```

The benchmark creates a temporary Git repository and removes it when finished.

## What it measures

- repository setup time;
- object count/sample size;
- one-process-per-request object reads;
- persistent `cat-file --batch` reads;
- repeated reads through the persistent worker.

The comparison is intentionally narrow. It does **not** yet measure tree traversal, commit creation, concurrent agents, ref CAS, filesystem checkouts, Redis, SQLite, or a real MCP transport.

## Interpretation

The interesting result is the ratio:

```text
cold subprocess time / persistent worker time
```

A strong advantage for the persistent worker would justify building the next prototype around a long-lived Git object worker. If the difference is small, we should benchmark the actual treeless operations before adding another layer.
