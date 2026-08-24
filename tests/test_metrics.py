from __future__ import annotations

import pytest

from personal_repo_mcp.metrics import Metrics


@pytest.mark.asyncio
async def test_metrics_middleware_records_tool_success_and_failure() -> None:
    metrics = Metrics()
    middleware = metrics.middleware()

    async def success(_ctx):
        return {"ok": True}

    class Ctx:
        method = "tools/call"
        params = {"name": "example", "arguments": {"x": 1}}

    await middleware(Ctx(), success)

    async def failure(_ctx):
        raise ValueError("boom")

    with pytest.raises(ValueError):
        await middleware(Ctx(), failure)

    snapshot = metrics.snapshot()
    assert snapshot.tool_calls == 2
    assert snapshot.tool_successes == 1
    assert snapshot.tool_failures == 1
    assert snapshot.tools["example"]["calls"] == 2
    assert snapshot.tools["example"]["successes"] == 1
    assert snapshot.tools["example"]["failures"] == 1
    assert snapshot.bytes_in > 0
    assert snapshot.bytes_out > 0


def test_metrics_resource_read_and_notification_counters() -> None:
    metrics = Metrics()
    metrics.record_message("resources/read", {"uri": "repo://foo/file/a"}, {"text": "x"}, duration_ms=1, failed=False)
    metrics.record_message("notifications/resources/updated", {"uri": "repo://foo/file/a"}, None, duration_ms=0, failed=False)

    snapshot = metrics.snapshot()
    assert snapshot.resource_reads == 1
    assert snapshot.notifications == 1
