from __future__ import annotations

from dataclasses import dataclass

from core.tenancy.normalization import require_tenant_id


CANON_TENANT_RUNTIME_LIMITS = True


@dataclass(frozen=True)
class TenantRuntimeLimits:
    tenant_id: str
    max_concurrent_runs: int = 1
    max_actions_per_run: int = 25
    max_effects_per_run: int = 10
    max_outbound_messages_per_day: int = 100
    max_publications_per_day: int = 20
    max_memory_writes_per_day: int = 1000
    max_connector_calls_per_hour: int = 2000
    max_daily_budget: float = 0.0
    allow_background_automation: bool = True
    require_human_approval_for_strategic_change: bool = True

    def validate(self) -> None:
        require_tenant_id(self.tenant_id)
        for field_name in (
            "max_concurrent_runs",
            "max_actions_per_run",
            "max_effects_per_run",
            "max_outbound_messages_per_day",
            "max_publications_per_day",
            "max_memory_writes_per_day",
            "max_connector_calls_per_hour",
        ):
            if int(getattr(self, field_name)) < 0:
                raise ValueError(f"{field_name} must be >= 0")
        if float(self.max_daily_budget) < 0:
            raise ValueError("max_daily_budget must be >= 0")

    def ensure_within(self, *, field_name: str, value: int | float) -> None:
        self.validate()
        if not hasattr(self, field_name):
            raise AttributeError(field_name)
        limit = getattr(self, field_name)
        if float(value) > float(limit):
            raise ValueError(
                f"{field_name} exceeded for tenant={self.tenant_id}: {value} > {limit}"
            )


__all__ = ["CANON_TENANT_RUNTIME_LIMITS", "TenantRuntimeLimits"]
