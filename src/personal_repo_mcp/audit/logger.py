from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class AuditLogger:
    logger: logging.Logger

    def record(self, *, principal: str, repository: str | None, operation: str, success: bool, duration_ms: float, path: str | None = None, ref: str | None = None) -> None:
        event: dict[str, Any] = {
            "principal": principal,
            "repository": repository,
            "operation": operation,
            "success": success,
            "duration_ms": round(duration_ms, 2),
        }
        if path is not None:
            event["path"] = path
        if ref is not None:
            event["ref"] = ref
        self.logger.info("audit %s", json.dumps(event, sort_keys=True, separators=(",", ":")))

    def timed(self, *, principal: str, repository: str | None, operation: str, path: str | None = None, ref: str | None = None):
        return _AuditTimer(self, principal, repository, operation, path, ref)


class _AuditTimer:
    def __init__(self, audit: AuditLogger, principal: str, repository: str | None, operation: str, path: str | None, ref: str | None) -> None:
        self.audit, self.principal, self.repository, self.operation, self.path, self.ref = audit, principal, repository, operation, path, ref
        self.started = 0.0

    def __enter__(self) -> "_AuditTimer":
        self.started = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.audit.record(principal=self.principal, repository=self.repository, operation=self.operation, success=exc_type is None, duration_ms=(time.perf_counter() - self.started) * 1000, path=self.path, ref=self.ref)
        return False
