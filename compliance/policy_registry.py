from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from compliance.base import CompliancePolicyError, PolicyMetadata


@dataclass(frozen=True)
class PolicySnapshot:
    policy_name: str
    policy_version: str
    tags: tuple[str, ...]
    metadata: Mapping[str, object]


class PolicyRegistry:
    """Metadata-only registry of active compliance policies."""

    def __init__(self) -> None:
        self._policies: dict[str, PolicyMetadata] = {}

    def register(self, metadata: PolicyMetadata) -> None:
        if not metadata.policy_name.strip():
            raise CompliancePolicyError('policy_name must be non-empty.')
        if not metadata.policy_version.strip():
            raise CompliancePolicyError('policy_version must be non-empty.')
        self._policies[metadata.policy_name] = metadata

    def get(self, policy_name: str) -> PolicyMetadata:
        try:
            return self._policies[policy_name]
        except KeyError as exc:
            raise CompliancePolicyError(f'Policy is not registered: {policy_name}') from exc

    def snapshot(self) -> tuple[PolicySnapshot, ...]:
        return tuple(
            PolicySnapshot(
                policy_name=item.policy_name,
                policy_version=item.policy_version,
                tags=item.tags,
                metadata=dict(item.metadata),
            )
            for item in sorted(self._policies.values(), key=lambda x: x.policy_name)
        )
