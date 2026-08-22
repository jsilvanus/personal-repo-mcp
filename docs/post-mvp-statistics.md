# Post-MVP Plan: Statistics and Usage Metrics

## Status

**Planned, post-MVP.** This feature adds operational statistics for MCP usage, Git activity, data transfer, repository storage, and system resources.

The design should remain implementation-neutral so we can begin with lightweight counters and filesystem/process inspection without committing the project to a full metrics or time-series platform.

## Goals

Provide agents and administrators with enough information to answer questions such as:

- How much has the MCP been used?
- Which tools are being used most?
- How many calls are failing?
- How much data is moving through MCP and Git?
- How much storage does each repository consume?
- How much disk space remains?
- Is the Docker service approaching its CPU, memory, or storage limits?
- How many Git clones/fetches/pushes have occurred?
- Is repository storage growing unexpectedly?

The feature should support both machine-readable MCP resources and human-oriented diagnostic output where useful.

## Design principles

1. **Observe without changing existing semantics.** Statistics must not alter the behavior of tools, resources, chains, or Git operations.
2. **Prefer resources for observation.** Statistics are state, not commands, so the primary interface should be MCP resources rather than a large collection of statistics tools.
3. **Keep stable and changing information separate.** A repository's basic resource should not change merely because a call counter or CPU value changed.
4. **Start lightweight.** Do not introduce Prometheus, a time-series database, or another external service until a concrete requirement justifies it.
5. **Respect the Docker boundary.** Report container-visible resources separately from host-wide resources when the distinction matters.
6. **Never expose secrets.** Statistics, errors, labels, and logs must pass through the existing secret-scrubbing policy.
7. **Make aggregation explicit.** System totals, per-repository statistics, and per-tool statistics should not be confused.
8. **Keep historical persistence optional.** Current state and process-lifetime counters should work without a database.

## Statistics categories

### 1. MCP usage

Track at least:

- total tool calls;
- calls by tool;
- successful calls;
- failed calls;
- execution time/latency;
- chain executions;
- chain failures;
- resource reads;
- resource subscriptions, if enabled;
- notification deliveries, if enabled.

Potential dimensions include repository and logical client/session identity where the MCP protocol provides a safe, non-sensitive identifier.

Do not record arbitrary user input merely for statistics.

### 2. Data transfer

Track logical MCP payload volume:

- bytes received by MCP;
- bytes sent by MCP;
- optionally per-tool input/output bytes;
- optionally per-resource read bytes.

For Git/SSH support, separately track:

- Git upload bytes;
- Git download bytes;
- clone/fetch/push operation counts.

Initially these can be logical payload/process-level measurements rather than exact network-interface accounting.

If compression makes wire-level accounting important later, introduce explicit wire/network metrics rather than silently redefining existing counters.

### 3. Repository storage

For each authorized repository, expose:

- working-tree size;
- `.git`/Git object database size;
- total repository size;
- file count;
- Git object count where practical;
- tracked file count;
- untracked file count;
- submodule/gitlink information where useful;
- last measured timestamp.

At system level expose:

- total repository storage;
- free storage available to the container;
- configured storage limit, if one exists;
- temporary storage usage where measurable.

Storage measurements should be clearly identified as measurements and need not be continuously recalculated on every resource read.

### 4. System/container resources

Expose current operational state such as:

- CPU usage;
- memory usage;
- disk usage/free space;
- process/resource pressure where available;
- uptime;
- container limits when discoverable.

The implementation should distinguish container-level values from host-wide values. The MCP should not claim to know unrestricted host capacity when Docker limits its effective resources.

## MCP resource model

Use a small hierarchy rather than many individual resources.

Conceptually:

```text
repo://system/statistics
repo://repo/<repository>/statistics
```

The system resource can contain:

```text
usage
resources
storage
transfer
git
```

A repository statistics resource can contain:

```text
storage
mcp_usage
git
transfer
```

The exact URI scheme must follow the resource naming conventions already established by the project.

### Changing data

Rapidly changing values such as CPU, memory, and current free disk should be represented as changing/statistical resources rather than modifying the fundamental repository metadata resource.

This preserves the previously established distinction between stable repository information and changing observations.

## Tool-level statistics

Tool-level counters should be available in the statistics resource, for example:

```text
tool_calls:
  read_file:
    calls: 3241
    successes: 3198
    failures: 43
    total_duration_ms: ...
  git_status:
    calls: 1822
    ...
```

Do not require every individual metric to be exposed as a separate MCP resource.

The implementation should retain enough internal structure to add aggregation dimensions later without changing the external resource format unnecessarily.

## Counters and lifecycle

The initial implementation should distinguish two kinds of values.

### Current state

Examples:

- current CPU;
- current memory;
- current disk usage;
- current repository size.

### Process-lifetime counters

Examples:

- tool calls since startup;
- bytes transferred since startup;
- errors since startup;
- Git operations since startup.

These counters reset when the service restarts unless persistent statistics are explicitly enabled later.

Expose the statistics start/reset timestamp so consumers can interpret counters correctly.

## Historical statistics

Historical metrics are intentionally a later phase.

Possible future data:

- hourly/daily tool-call totals;
- weekly data transfer;
- storage growth;
- failure-rate trends;
- Git activity over time;
- resource utilization over time.

Do not add a database solely to support these until the need is demonstrated.

If historical persistence is added, prefer a small embedded store initially and keep the external MCP resource model independent of the storage implementation.

## Agent usefulness

The statistics resource should be compact enough for an agent to inspect when making operational decisions.

For example, an agent considering a large clone should be able to determine:

```text
available storage
configured storage limit
current repository usage
recent Git activity
```

An agent investigating a failed operation should be able to correlate:

```text
recent failures
latency/resource pressure
repository state
```

The resource/help documentation should explain when statistics are useful, but agents should not be forced to read large historical datasets merely to obtain current capacity information.

## Relationship to resources and subscriptions

If resource subscriptions/notifications are implemented, statistics are a natural consumer of that mechanism, but subscriptions should be selective.

Do not emit notifications for every CPU fluctuation or every individual call.

Suitable future subscription events could include:

- storage crossing a configured threshold;
- repository size crossing a threshold;
- repeated tool failures;
- service resource pressure;
- Git operation failures.

These should be event/threshold based rather than continuous telemetry streams.

## Relationship to Git SSH access

The planned restricted SSH Git transport should contribute Git-specific statistics without changing the general MCP statistics model.

For example:

```text
Git operations
  clone/fetch
  push
  upload bytes
  download bytes
  failures
```

The SSH transport should identify the logical repository and authorized key/user without recording private keys or sensitive authentication material.

## Relationship to treeless Git workers

Future treeless workers may produce Git objects without changing the working tree.

Statistics should therefore distinguish where useful between:

- working-tree Git operations;
- object-level/treeless operations;
- ref updates;
- worker activity.

Do not make statistics depend on the presence of treeless workers. The basic model must work before that feature exists.

Potential future metrics:

```text
worker commits created
objects created
ref CAS successes
ref CAS conflicts
patch failures
```

## Security and privacy

Statistics are operational metadata and can reveal information about repository activity.

Apply the same repository authorization boundary to repository-specific statistics as to repository tools/resources.

Do not expose:

- PATs;
- SSH private keys;
- API credentials;
- environment secrets;
- raw command-line arguments containing secrets;
- sensitive file contents.

Error labels and diagnostic fields must pass through existing secret scrubbing.

If client/session identifiers are eventually included, use the least identifying stable identifier necessary for aggregation.

## Storage measurement strategy

Repository size calculation can be relatively expensive for large repositories. Do not recursively calculate every repository's complete size on every statistics read.

Prefer:

1. cached measurements;
2. explicit refresh/invalidation after operations that change repository contents;
3. periodic background measurement if later needed;
4. an explicit refresh mechanism only if required.

The initial implementation can use filesystem statistics and Git plumbing commands where appropriate.

## Docker limits

The statistics implementation should report the effective container-visible limits when possible.

For example:

```text
CPU:
  current usage
  configured limit

Memory:
  current usage
  configured limit

Storage:
  used
  available
  configured repository/storage limit
```

This becomes particularly important if Docker storage quotas or CPU/memory limits are introduced later.

Do not treat host free disk as available repository capacity if the container has a smaller effective limit.

## Implementation phases

### Phase 1 — Current state

Implement:

- CPU;
- memory;
- disk usage/free space;
- uptime;
- per-repository size;
- Git object/storage size where practical;
- container limits where available;
- `repo://system/statistics`;
- `repo://repo/<repository>/statistics`.

### Phase 2 — MCP counters

Add:

- tool call counters;
- success/failure counts;
- latency;
- bytes in/out;
- resource reads;
- chain statistics;
- process start/reset timestamp.

### Phase 3 — Git/SSH activity

Add:

- clone/fetch/push counts;
- Git transfer volume;
- SSH connection counts;
- SSH failures;
- per-repository Git activity.

### Phase 4 — Threshold notifications

If notifications/subscriptions are stable and useful, add threshold/event notifications for:

- low disk space;
- storage quota pressure;
- repeated failures;
- resource pressure;
- unusually large repositories.

### Phase 5 — Historical metrics

Only if required:

- persistent counters;
- daily/weekly summaries;
- storage growth;
- activity history;
- resource utilization history.

The external resource schema should remain compatible as the backing store evolves.

## Testing

Test at least:

- counters increment exactly once per operation;
- failed operations are counted correctly;
- chain operations are represented consistently;
- resource reads do not themselves create recursive/infinite statistics noise;
- repository statistics respect repository authorization;
- secret scrubbing applies to errors/labels;
- large repositories do not cause unacceptable statistics latency;
- storage measurements correctly account for configured Docker limits;
- statistics remain correct across repository creation/deletion;
- counters reset correctly on restart;
- historical storage, if added, does not block normal MCP operation.

## Explicit non-goals

- no external monitoring platform in the first implementation;
- no Prometheus dependency initially;
- no full time-series database initially;
- no per-file access telemetry by default;
- no recording of request contents for analytics;
- no unrestricted host monitoring;
- no automatic alerting service;
- no requirement to persist every individual event forever.

## Completion criteria

The feature is complete when an authorized agent can inspect the statistics resources and reliably determine:

1. how much the MCP has been used;
2. which tools are consuming activity;
3. how many operations have failed;
4. how much data has moved;
5. how much storage each repository consumes;
6. how much effective storage remains;
7. current container resource pressure;
8. Git/SSH activity once those transports exist.

The implementation should remain small enough that statistics themselves cannot become a significant source of resource consumption.