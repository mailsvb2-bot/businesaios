from __future__ import annotations

from dataclasses import dataclass

from core.finance.money import legacy_float, money_decimal
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

    def __post_init__(self) -> None:
        normalized_budget = money_decimal(
            self.max_daily_budget,
            name="max_daily_budget",
        )
        object.__setattr__(
            self,
            "max_daily_budget",
            legacy_float(normalized_budget, name="max_daily_budget"),
        )

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
            value = getattr(self, field_name)
            if isinstance(value, bool) or int(value) != value or int(value) < 0:
                raise ValueError(f"{field_name} must be a non-negative integer")
        money_decimal(self.max_daily_budget, name="max_daily_budget")

    def ensure_within(self, *, field_name: str, value: int | float) -> None:
        self.validate()
        if not hasattr(self, field_name):
            raise AttributeError(field_name)
        limit = getattr(self, field_name)
        if field_name == "max_daily_budget":
            requested_budget = money_decimal(value, name=field_name)
            limit_budget = money_decimal(limit, name=field_name)
            exceeded = requested_budget > limit_budget
        else:
            if isinstance(value, bool) or int(value) != value:
                raise ValueError(f"{field_name} must be an integer")
            exceeded = int(value) > int(limit)
        if exceeded:
            raise ValueError(
                f"{field_name} exceeded for tenant={self.tenant_id}: {value} > {limit}"
            )


__all__ = ["CANON_TENANT_RUNTIME_LIMITS", "TenantRuntimeLimits"]
