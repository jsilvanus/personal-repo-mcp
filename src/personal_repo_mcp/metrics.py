from __future__ import annotations

import json
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ToolMetric:
    calls: int = 0
    successes: int = 0
    failures: int = 0
    total_duration_ms: float = 0.0
    max_duration_ms: float = 0.0
    bytes_in: int = 0
    bytes_out: int = 0


@dataclass(slots=True)
class MetricsSnapshot:
    started_at: float
    messages: int
    tool_calls: int
    tool_successes: int
    tool_failures: int
    total_duration_ms: float
    max_duration_ms: float
    bytes_in: int
    bytes_out: int
    resource_reads: int
    notifications: int
    tools: dict[str, dict[str, Any]] = field(default_factory=dict)


class Metrics:
    """Small process-lifetime metrics collector.

    Statistics intentionally live in memory for now. The collector is independent
    of MCP transport so a persistent backend can be added later without changing
    the statistics resource contract.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._started_at = time.time()
        self._messages = 0
        self._tool_calls = 0
        self._tool_successes = 0
        self._tool_failures = 0
        self._total_duration_ms = 0.0
        self._max_duration_ms = 0.0
        self._bytes_in = 0
        self._bytes_out = 0
        self._resource_reads = 0
        self._notifications = 0
        self._tools: dict[str, ToolMetric] = defaultdict(ToolMetric)

    @staticmethod
    def _size(value: Any) -> int:
        try:
            return len(json.dumps(value, default=str, separators=(",", ":")).encode("utf-8"))
        except (TypeError, ValueError):
            return 0

    def record_message(self, method: str, params: Any, result: Any, *, duration_ms: float, failed: bool) -> None:
        with self._lock:
            self._messages += 1
            self._bytes_in += self._size(params)
            self._bytes_out += self._size(result)
            if method == "resources/read":
                self._resource_reads += 1
            if method.startswith("notifications/"):
                self._notifications += 1
            if method != "tools/call":
                return

            name = "unknown"
            if isinstance(params, dict):
                name = str(params.get("name") or "unknown")
            metric = self._tools[name]
            metric.calls += 1
            metric.total_duration_ms += duration_ms
            metric.max_duration_ms = max(metric.max_duration_ms, duration_ms)
            metric.bytes_in += self._size(params)
            metric.bytes_out += self._size(result)
            self._tool_calls += 1
            self._total_duration_ms += duration_ms
            self._max_duration_ms = max(self._max_duration_ms, duration_ms)
            if failed:
                metric.failures += 1
                self._tool_failures += 1
            else:
                metric.successes += 1
                self._tool_successes += 1

    def middleware(self):
        async def record(ctx, call_next):
            started = time.perf_counter()
            failed = False
            result = None
            try:
                result = await call_next(ctx)
                return result
            except Exception:
                failed = True
                raise
            finally:
                duration_ms = (time.perf_counter() - started) * 1000
                self.record_message(ctx.method, getattr(ctx, "params", None), result, duration_ms=duration_ms, failed=failed)

        return record

    def snapshot(self) -> MetricsSnapshot:
        with self._lock:
            tools = {
                name: {
                    "calls": metric.calls,
                    "successes": metric.successes,
                    "failures": metric.failures,
                    "total_duration_ms": round(metric.total_duration_ms, 2),
                    "max_duration_ms": round(metric.max_duration_ms, 2),
                    "bytes_in": metric.bytes_in,
                    "bytes_out": metric.bytes_out,
                }
                for name, metric in sorted(self._tools.items())
            }
            return MetricsSnapshot(
                started_at=self._started_at,
                messages=self._messages,
                tool_calls=self._tool_calls,
                tool_successes=self._tool_successes,
                tool_failures=self._tool_failures,
                total_duration_ms=round(self._total_duration_ms, 2),
                max_duration_ms=round(self._max_duration_ms, 2),
                bytes_in=self._bytes_in,
                bytes_out=self._bytes_out,
                resource_reads=self._resource_reads,
                notifications=self._notifications,
                tools=tools,
            )
