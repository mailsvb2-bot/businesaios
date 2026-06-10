from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

CANON_CONNECTOR_SANDBOX = True


@dataclass(frozen=True)
class ConnectorSandboxPolicy:
    connector_id: str
    allow_network: bool = False
    allow_mutations: bool = False
    allowed_operations: tuple[str, ...] = field(default_factory=tuple)
    blocked_operations: tuple[str, ...] = field(default_factory=tuple)
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        connector_id = str(self.connector_id or '').strip()
        if not connector_id:
            raise ValueError('connector_id is required')
        object.__setattr__(self, 'connector_id', connector_id)
        object.__setattr__(
            self,
            'allowed_operations',
            tuple(sorted({str(item).strip() for item in self.allowed_operations if str(item).strip()})),
        )
        object.__setattr__(
            self,
            'blocked_operations',
            tuple(sorted({str(item).strip() for item in self.blocked_operations if str(item).strip()})),
        )

    def allows(self, *, operation: str, dry_run: bool, requires_network: bool = True) -> bool:
        op = str(operation or '').strip()
        if not op:
            return False
        if op in set(self.blocked_operations):
            return False
        if self.allowed_operations and op not in set(self.allowed_operations):
            return False
        if requires_network and not self.allow_network:
            return False
        if dry_run:
            return True
        return bool(self.allow_mutations)


class ConnectorSandbox:
    def __init__(self, policies: tuple[ConnectorSandboxPolicy, ...] = ()) -> None:
        self._policies: dict[str, ConnectorSandboxPolicy] = {str(item.connector_id): item for item in policies}

    def register(self, policy: ConnectorSandboxPolicy) -> None:
        self._policies[str(policy.connector_id)] = policy

    def require_allowed(
        self,
        *,
        connector_id: str,
        operation: str,
        dry_run: bool,
        requires_network: bool = True,
    ) -> None:
        policy = self._policies.get(str(connector_id))
        if policy is None:
            if dry_run:
                return
            raise PermissionError(f'no sandbox policy for connector={connector_id}')
        if not policy.allows(operation=operation, dry_run=dry_run, requires_network=requires_network):
            raise PermissionError(
                f'connector sandbox rejected connector={connector_id} operation={operation} dry_run={dry_run} requires_network={requires_network}'
            )

    def is_allowed(
        self,
        *,
        connector_id: str,
        operation: str,
        dry_run: bool,
        requires_network: bool = True,
    ) -> bool:
        try:
            self.require_allowed(
                connector_id=connector_id,
                operation=operation,
                dry_run=dry_run,
                requires_network=requires_network,
            )
        except PermissionError:
            return False
        return True


__all__ = [
    'CANON_CONNECTOR_SANDBOX',
    'ConnectorSandbox',
    'ConnectorSandboxPolicy',
]
