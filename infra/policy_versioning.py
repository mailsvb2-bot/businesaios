from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PolicyVersion:
    version_id: str
    policy_name: str
    metadata: dict = field(default_factory=dict)


@dataclass
class PolicyVersionRegistry:
    _versions: dict[str, PolicyVersion] = field(default_factory=dict)

    def register(self, version: PolicyVersion) -> None:
        self._versions[version.version_id] = version

    def get(self, version_id: str) -> PolicyVersion:
        return self._versions[version_id]

    def list_versions(self) -> tuple[PolicyVersion, ...]:
        return tuple(self._versions.values())
