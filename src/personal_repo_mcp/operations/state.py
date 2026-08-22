from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum


class OperationStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(slots=True)
class Operation:
    id: str
    repository: str
    kind: str
    status: OperationStatus = OperationStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    result: object | None = None
    error: str | None = None


class OperationStore:
    def __init__(self) -> None:
        self._items: dict[str, Operation] = {}

    def put(self, operation: Operation) -> Operation:
        self._items[operation.id] = operation
        return operation

    def get(self, operation_id: str) -> Operation:
        try:
            return self._items[operation_id]
        except KeyError as exc:
            raise KeyError(f"Unknown operation: {operation_id}") from exc
