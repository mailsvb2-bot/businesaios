"""Canonical Experiment Engine runtime wiring.

The Experiment domain stays in core.experiments. Runtime wiring only binds
its repositories to the existing canonical Event Store; it owns no experiment
semantics and creates no parallel source of truth.
"""

from __future__ import annotations

from core.experiments.repositories.event_store_repository import (
    EventStoreAssignmentRepository,
    EventStoreExperimentRepository,
    EventStoreResultRepository,
)
from core.experiments.service import ExperimentsService

CANON_BOOT_WIRING_ONLY = True
CANON_EXPERIMENTS_RUNTIME_WIRING = True


def build_experiments_service(
    *,
    event_store,
    tenant_id: str,
    business_id: str,
) -> ExperimentsService:
    scope = {
        "event_store": event_store,
        "tenant_id": str(tenant_id or "").strip(),
        "business_id": str(business_id or "").strip(),
    }
    return ExperimentsService(
        experiment_repository=EventStoreExperimentRepository(**scope),
        assignment_repository=EventStoreAssignmentRepository(**scope),
        result_repository=EventStoreResultRepository(**scope),
    )


def register_experiments_routes(app: object) -> object:
    """Compatibility hook.

    Experiment mutation is intentionally not exposed through an ungoverned
    direct route. Launches enter through the canonical RuntimeExecutor action
    path, where ActionIntent/PolicyDecision authorization already applies.
    """

    return app


__all__ = [
    "CANON_BOOT_WIRING_ONLY",
    "CANON_EXPERIMENTS_RUNTIME_WIRING",
    "build_experiments_service",
    "register_experiments_routes",
]
