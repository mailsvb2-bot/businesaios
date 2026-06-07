from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

Json = dict[str, Any]


@dataclass(frozen=True)
class AdsGuardrails:
    dry_run: bool = True
    plan_only: bool = True
    apply_enabled: bool = False

    max_daily_budget: float = 0.0
    allowed_platforms: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AdsCommand:
    platform: str
    action: str
    payload: Json


@dataclass(frozen=True)
class AdsPlan:
    commands: list[AdsCommand]
    notes: str = ""


class AdsPort(Protocol):
    def draft_plan(self, tenant_id: str, spec: Json) -> AdsPlan: ...
    def read_metrics(self, tenant_id: str, query: Json) -> Json: ...


class AdsService:
    """Canonical Ads facade.

    Core remains proposal-only:
    - build_plan() drafts a typed plan
    - metrics() reads snapshots through an injected read port
    - apply_plan() never performs writes; runtime apply goes only through
      execute_plan@v1 -> AdsApplyEngine -> AdsWriteGateway
    """

    def __init__(self, port: AdsPort, guardrails: AdsGuardrails) -> None:
        self._port = port
        self._g = guardrails

    def build_plan(self, tenant_id: str, spec: Json) -> AdsPlan:
        return self._port.draft_plan(tenant_id, spec)

    def apply_plan(self, tenant_id: str, plan: AdsPlan) -> Json:
        return {
            "status": "deferred",
            "reason": "runtime_apply_required",
            "dry_run": self._g.dry_run,
            "plan_only": self._g.plan_only,
            "apply_enabled": self._g.apply_enabled,
            "tenant_id": str(tenant_id),
            "commands": len(list(plan.commands or [])),
        }

    def metrics(self, tenant_id: str, query: Json) -> Json:
        return self._port.read_metrics(tenant_id, query)
