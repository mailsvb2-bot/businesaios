from __future__ import annotations

import importlib
import sys

_COMPAT_MODULES = {
    "assignment": "core.experiments.builders.live_canary_assignment",
    "guardrails": "core.experiments.guards.live_canary_guardrails",
    "ledger": "core.experiments.repositories.live_canary_ledger",
    "live_canary_events": "core.experiments.events.live_canary_events",
    "statistics": "core.experiments.evaluators.live_canary_statistics",
}
for _legacy_name, _canonical_name in _COMPAT_MODULES.items():
    sys.modules[f"{__name__}.{_legacy_name}"] = importlib.import_module(_canonical_name)

from core.experiments.builders.experiment_plan_builder import (  # noqa: E402
    ExperimentPlanBuilder,
    build_experiment,
)
from core.experiments.builders.live_canary_assignment import (  # noqa: E402
    ExperimentArm,
    ExperimentAssignment,
    StableExperimentAssigner,
)
from core.experiments.guard import ExperimentsGuard  # noqa: E402
from core.experiments.guards.live_canary_guardrails import (  # noqa: E402
    CanaryDecision,
    GuardrailResult,
    LiveCanaryGuard,
)
from core.experiments.repositories.live_canary_ledger import LiveCanaryLedger  # noqa: E402
from core.experiments.service import ExperimentsService, build_empty_result  # noqa: E402

__all__ = [
    "CanaryDecision",
    "ExperimentArm",
    "ExperimentAssignment",
    "ExperimentPlanBuilder",
    "ExperimentsGuard",
    "ExperimentsService",
    "GuardrailResult",
    "LiveCanaryGuard",
    "LiveCanaryLedger",
    "StableExperimentAssigner",
    "build_empty_result",
    "build_experiment",
]
