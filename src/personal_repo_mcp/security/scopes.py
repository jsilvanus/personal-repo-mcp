from __future__ import annotations

from dataclasses import dataclass

from .policy import Policy


@dataclass(frozen=True, slots=True)
class Scope:
    principal: str
    repositories: frozenset[str] | None = None
    policy: Policy = Policy()

    def check_repository(self, repository: str) -> None:
        if self.repositories is not None and repository not in self.repositories:
            raise PermissionError(f"Repository access denied: {repository}")

    def check(self, repository: str, operation: str) -> None:
        self.check_repository(repository)
        self.policy.check(operation)


def scope_from_token(token: str | None) -> Scope:
    # Phase 1 has one bearer token. Keep the abstraction ready for scoped tokens.
    return Scope(principal="bearer", repositories=None, policy=Policy())
