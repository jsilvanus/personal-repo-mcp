# Resources and subscriptions

Phase 5 adds standard MCP Resources and the 2026-07-28 `subscriptions/listen` change mechanism.

## URI namespace

Resources are repository-scoped:

```text
repo://<repository>/file/<path>
repo://<repository>/git/status
repo://<repository>/git/diff
repo://<repository>/git/conflicts
repo://<repository>/tests/<run-id>       # reserved
repo://<repository>/artifacts/<id>       # reserved
```

Files are persistent workspace resources and include untracked files. `.git` is never exposed as a file resource.

## File resources

The file resource is a URI template:

```text
repo://{repository}/file/{+path}
```

The current implementation returns JSON containing the file URI, path, byte size, SHA-256 hash, and UTF-8 content. Files larger than 10 MiB and binary files should continue to use the Phase 2 file tools instead.

## Git resources

The following resources expose current read-only state:

- `git/status` — branch and porcelain working-tree/index status
- `git/diff` — current unstaged diff
- `git/conflicts` — structured conflict state

Git tools remain the mutation interface.

## Subscriptions

The server uses the Python SDK v2 subscription bus and standard `subscriptions/listen`. Mutating filesystem tools publish `notifications/resources/updated` for the changed file plus Git status/diff. The notification contains only the URI; clients re-read the resource to obtain current state.

The SDK filters notifications to clients that explicitly subscribed to the URI. There is no replay queue.

## Concurrency

File resources expose SHA-256 content hashes. Agents can use the hash as the `expected_hash` for Phase 2 writes. A resource update therefore provides awareness, while the existing expected-hash check provides stale-write protection.

## Future resources

Test-run and build-artifact URIs are reserved now so later phases can add producers without changing the namespace. Test execution, artifact downloads, filesystem watching, and Tasks are intentionally outside Phase 5.
