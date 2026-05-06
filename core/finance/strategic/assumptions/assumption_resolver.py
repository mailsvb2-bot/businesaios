from __future__ import annotations

from decimal import Decimal

from core.finance.strategic.assumptions.assumption_audit_log import AssumptionAuditLog
from core.finance.strategic.assumptions.assumption_registry import AssumptionRegistry


class AssumptionResolver:
    def __init__(self, registry: AssumptionRegistry | None = None, audit_log: AssumptionAuditLog | None = None) -> None:
        self._registry = registry or AssumptionRegistry()
        self._audit_log = audit_log

    def resolve(self, explicit: dict[str, Decimal], *, actor: str = "strategic_finance") -> dict[str, Decimal]:
        resolved = self._registry.defaults()
        normalized = {key: Decimal(str(value)) for key, value in explicit.items()}
        if self._audit_log is not None:
            for key, new_value in normalized.items():
                old_value = resolved.get(key)
                if old_value != new_value:
                    self._audit_log.record(key=key, old_value=old_value, new_value=new_value, actor=actor)
        resolved.update(normalized)
        return resolved
