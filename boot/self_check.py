from __future__ import annotations

from typing import Protocol, runtime_checkable

from canon.anti_second_brain_rules import FORBIDDEN_DECISION_CLASS_NAMES
from canon.invariants import default_invariants
from config.system_config import CANONICAL_OBJECTIVE_NAME

CANON_BOOT_SELF_CHECK_INTERNAL_SUPPORT = True
CANON_BOOT_SELF_CHECK_NO_PUBLIC_ENTRYPOINT = True
CANON_BOOT_SELF_CHECK_NO_RUNTIME_ASSEMBLY = True


@runtime_checkable
class SupportsBootSelfCheck(Protocol):
    readiness: object
    services: object
    components: object


def run_self_check(orchestrator: SupportsBootSelfCheck) -> None:
    invariants = default_invariants()
    if not invariants:
        raise RuntimeError("canon self-check failed: no invariants registered")

    descriptions = " ".join(item.description for item in invariants)
    if "DecisionCore" not in descriptions:
        raise RuntimeError("canon self-check failed: no decision-core invariant")
    if CANONICAL_OBJECTIVE_NAME not in descriptions and "profit-adjusted growth" not in descriptions:
        raise RuntimeError("canon self-check failed: no shared optimization objective invariant")
    if "DecisionCore" in FORBIDDEN_DECISION_CLASS_NAMES:
        raise RuntimeError("canon self-check failed: corrupted second-brain rule set")
    if orchestrator.readiness is None:
        raise RuntimeError("canon self-check failed: missing readiness service")
    if len(orchestrator.services) == 0 or len(orchestrator.components) == 0:
        raise RuntimeError("canon self-check failed: runtime registries are empty")
