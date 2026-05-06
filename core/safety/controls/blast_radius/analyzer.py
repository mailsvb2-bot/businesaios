from __future__ import annotations

from ..action_catalog import ActionSafetyCatalog, build_default_action_catalog
from .models import BlastRadiusEstimate
from ..action_context import SafetyActionContext


class StaticBlastRadiusAnalyzer:
    def __init__(self, catalog: ActionSafetyCatalog | None = None) -> None:
        self._catalog = catalog or build_default_action_catalog()

    def estimate(self, ctx: SafetyActionContext) -> BlastRadiusEstimate:
        payload = dict(ctx.payload)
        spec = self._catalog.resolve(ctx.action)
        financial_amount = float(payload.get("amount", payload.get("budget_delta", payload.get("financial_amount", 0.0))) or 0.0)
        users_affected = int(payload.get("audience_size", payload.get("users_affected", 0)) or 0)
        records_affected = int(payload.get("records", payload.get("records_affected", 0)) or 0)
        services_touched = int(payload.get("services_touched", 1) or 0)
        if spec is not None:
            financial_amount = max(financial_amount, float(spec.blast_financial_amount or 0.0))
            users_affected = max(users_affected, int(spec.blast_users_affected or 0))
            records_affected = max(records_affected, int(spec.blast_records_affected or 0))
            services_touched = max(services_touched, int(spec.blast_services_touched or 0))
        return BlastRadiusEstimate(
            financial_amount=financial_amount,
            users_affected=users_affected,
            records_affected=records_affected,
            services_touched=services_touched,
        )
