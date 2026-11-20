from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from acquisition import (
    AcquisitionFeasibilityRequest,
    AcquisitionHeadlessEntrypoint,
    create_acquisition_headless_entrypoint,
)
from presentation import AcquisitionViewModel, build_acquisition_view_model

CANON_HEADLESS_ACQUISITION_EXECUTION = True


@dataclass(frozen=True, slots=True)
class HeadlessAcquisitionExecution:
    """Canonical headless boundary for acquisition calculations.

    Important:
    - no duplicated acquisition math
    - no parallel decision logic
    - no UI rendering side effects
    """

    entrypoint: AcquisitionHeadlessEntrypoint

    def execute(self, payload: Mapping[str, Any] | AcquisitionFeasibilityRequest) -> AcquisitionViewModel:
        return build_acquisition_view_model(self.entrypoint.evaluate(payload))


def create_headless_acquisition_execution(
    *,
    entrypoint: AcquisitionHeadlessEntrypoint | None = None,
) -> HeadlessAcquisitionExecution:
    return HeadlessAcquisitionExecution(entrypoint=entrypoint or create_acquisition_headless_entrypoint())


def execute_headless_acquisition(
    payload: Mapping[str, Any] | AcquisitionFeasibilityRequest,
    *,
    entrypoint: AcquisitionHeadlessEntrypoint | None = None,
) -> AcquisitionViewModel:
    return create_headless_acquisition_execution(entrypoint=entrypoint).execute(payload)


def promotion_launch_preview(*, plan: Mapping[str, Any], sustainable: bool, provider: str,
                             connectors: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """Pure review of the existing acquisition plan; never sends or spends."""
    daily = plan.get("recommended_daily_budget")
    daily_ok = isinstance(daily, int | float) and not isinstance(daily, bool) and 0 < daily < 1e12
    weekly_cap_minor = int(round(float(daily) * 7 * 100)) if daily_ok else 0
    capabilities = connectors.get(provider) or {}
    checks = [
        ("plan_feasible", bool(plan.get("feasible"))),
        ("economics_sustainable", bool(sustainable)),
        ("budget_cap_positive", weekly_cap_minor > 0),
        ("provider_known", bool(capabilities)),
        ("provider_write_capability", bool(capabilities.get("write"))),
        ("provider_verification_capability", bool(capabilities.get("verify"))),
        ("provider_production_ready", bool(capabilities.get("production_ready"))),
    ]
    blockers = [name for name, ok in checks if not ok]
    return {"mode": "dry_run", "provider": provider, "weekly_cap_minor": weekly_cap_minor, "currency": "RUB",
            "checks": [{"check": name, "passed": ok} for name, ok in checks], "blockers": blockers,
            "steps": ["ad_draft", "owner_approval_exact_cap", "provider_verification", "executor_publish"],
            "requires_human_approval": True, "apply_possible": not blockers,
            "spend_authorized": False, "provider_contacted": False}


__all__ = [
    'CANON_HEADLESS_ACQUISITION_EXECUTION', 'promotion_launch_preview', 'HeadlessAcquisitionExecution',
    'create_headless_acquisition_execution', 'execute_headless_acquisition',
]
