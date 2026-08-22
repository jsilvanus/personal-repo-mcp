from __future__ import annotations

import asyncio
import uuid

from .state import Operation, OperationStatus, OperationStore


class TaskRunner:
    """Small async operation runner; MCP Tasks can be layered on this state later."""

    def __init__(self, store: OperationStore | None = None) -> None:
        self.store = store or OperationStore()

    async def submit(self, repository: str, kind: str, operation) -> Operation:
        item = self.store.put(Operation(id=str(uuid.uuid4()), repository=repository, kind=kind, status=OperationStatus.RUNNING))
        try:
            item.result = await operation()
            item.status = OperationStatus.SUCCEEDED
        except asyncio.CancelledError:
            item.status = OperationStatus.CANCELLED
            raise
        except Exception as exc:
            item.status = OperationStatus.FAILED
            item.error = str(exc)
        return item
