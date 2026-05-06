from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

CANON_REGISTRY_CAPABILITY_CONTRACT = True
_ALLOWED_STATUSES = frozenset({"implemented", "not_implemented"})


@dataclass(frozen=True)
class RegistryCapabilityEntry:
    name: str
    status: str
    read: bool = False
    write: bool = False
    verify: bool = False
    supports_dry_run: bool = False
    supports_idempotency: bool = False
    production_ready: bool = False
    reversible: bool = False
    requires_human_approval: bool = True
    action_types: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        status = str(self.status or "").strip().lower()
        if status not in _ALLOWED_STATUSES:
            raise ValueError(f"unsupported registry status: {self.status}")
        if self.production_ready and not (self.write and self.verify and status == "implemented"):
            raise ValueError("production_ready connectors must be implemented with write and verify paths")

    def as_dict(self) -> dict[str, Any]:
        implemented = self.status == "implemented"
        truth_layer = {
            "implemented": bool(implemented),
            "stub": not bool(implemented),
            "write_enabled": bool(self.write),
            "verify_enabled": bool(self.verify),
            "dry_run_enabled": bool(self.supports_dry_run),
            "idempotent": bool(self.supports_idempotency),
            "reversible": bool(self.reversible),
            "requires_human_approval": bool(self.requires_human_approval),
        }
        return {
            "name": str(self.name),
            "status": str(self.status),
            "implemented": bool(implemented),
            "stub": not bool(implemented),
            "read": bool(self.read),
            "write": bool(self.write),
            "verify": bool(self.verify),
            "supports_dry_run": bool(self.supports_dry_run),
            "supports_idempotency": bool(self.supports_idempotency),
            "production_ready": bool(self.production_ready),
            "reversible": bool(self.reversible),
            "requires_human_approval": bool(self.requires_human_approval),
            "action_types": list(self.action_types),
            "truth_layer": truth_layer,
        }


def build_registry_entry(**kwargs: Any) -> dict[str, Any]:
    return RegistryCapabilityEntry(**kwargs).as_dict()
