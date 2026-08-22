from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ChainCommand:
    tool: str
    arguments: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ChainPolicy:
    on_error: str = "stop"
    max_commands: int = 32

    def validate(self) -> None:
        if self.on_error not in {"stop", "continue"}:
            raise ValueError("on_error must be 'stop' or 'continue'")
        if not 1 <= self.max_commands <= 100:
            raise ValueError("max_commands must be between 1 and 100")
