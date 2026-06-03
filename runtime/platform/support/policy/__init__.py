from __future__ import annotations

"""Canonical package owner for policy support surfaces."""

import json
from dataclasses import asdict, dataclass, is_dataclass
from pathlib import Path
from typing import Any, Protocol
from collections.abc import Mapping

from core.ai.policy_registry import PolicyRegistry
from runtime.platform.support.contracts.action import Action
from runtime.platform.support.contracts.observation import Observation


class Policy(Protocol):
    def act(self, observation: Observation) -> Action:
        ...

class Versioned(Protocol):
    @property
    def version(self) -> str:
        ...

@dataclass(frozen=True)
class PolicyCapabilities:
    supports_batch: bool = False
    supports_streaming: bool = False
    supports_deterministic: bool = True

class PolicyComparison:
    def better(self, left_score: float, right_score: float) -> bool:
        return left_score > right_score

@dataclass(frozen=True)
class PolicyConstraints:
    deterministic_only: bool = False
    max_latency_ms: int | None = None

class PolicyFactory:
    def __init__(self, registry: PolicyRegistry) -> None:
        self._registry = registry

    def create(self, name: str):
        return self._registry.get(name)

@dataclass(frozen=True)
class PolicyIdentity:
    name: str
    version: str = "1"

class PolicyLoader:
    """Small local loader for policy descriptors and plain JSON policies."""

    def load(self, path: str | Path) -> Any:
        return json.loads(Path(path).read_text(encoding="utf-8"))

@dataclass(frozen=True)
class PolicyMetadata:
    created_by: str | None = None
    tags: Mapping[str, Any] | None = None

class PolicyPackaging:
    def package(self, artifact_uri: str) -> dict[str, str]:
        return {"artifact_uri": artifact_uri}

class PolicySaver:
    """Small local saver for policy descriptors and plain JSON policies."""

    def save(self, path: str | Path, payload: Any) -> None:
        if is_dataclass(payload):
            payload = asdict(payload)
        Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

class PolicySelection:
    def choose_policy(self, policies):
        return policies[0]

    select = choose_policy

class PolicyVersioning:
    def __init__(self) -> None:
        self._versions: dict[str, int] = {}

    def next_version(self, policy_name: str) -> int:
        version = self._versions.get(policy_name, 0) + 1
        self._versions[policy_name] = version
        return version

__all__ = [
    "Policy",
    "PolicyCapabilities",
    "PolicyComparison",
    "PolicyConstraints",
    "PolicyFactory",
    "PolicyIdentity",
    "PolicyLoader",
    "PolicyMetadata",
    "PolicyPackaging",
    "PolicyRegistry",
    "PolicySaver",
    "PolicySelection",
    "PolicyVersioning",
    "Versioned",
]

_MODULE_EXPORTS = {
    "contracts": {"Policy": f"{__name__}:Policy"},
    "interfaces": {"Versioned": f"{__name__}:Versioned"},
    "policy_capabilities": {"PolicyCapabilities": f"{__name__}:PolicyCapabilities"},
    "policy_comparison": {"PolicyComparison": f"{__name__}:PolicyComparison"},
    "policy_constraints": {"PolicyConstraints": f"{__name__}:PolicyConstraints"},
    "policy_factory": {"PolicyFactory": f"{__name__}:PolicyFactory"},
    "policy_identity": {"PolicyIdentity": f"{__name__}:PolicyIdentity"},
    "policy_loader": {"PolicyLoader": f"{__name__}:PolicyLoader"},
    "policy_metadata": {"PolicyMetadata": f"{__name__}:PolicyMetadata"},
    "policy_packaging": {"PolicyPackaging": f"{__name__}:PolicyPackaging"},
    "policy_registry": {"PolicyRegistry": "core.ai.policy_registry:PolicyRegistry"},
    "policy_saver": {"PolicySaver": f"{__name__}:PolicySaver"},
    "policy_selection": {"PolicySelection": f"{__name__}:PolicySelection"},
    "policy_versioning": {"PolicyVersioning": f"{__name__}:PolicyVersioning"},
}
