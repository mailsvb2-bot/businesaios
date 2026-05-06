from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from governance.version import CONSTITUTION_VERSION


class ConstitutionViolation(Exception):
    """Фатальное нарушение законов системы."""
    pass


class DecisionEnvelopeLike(Protocol):
    decision_id: str
    signature: str


@dataclass(frozen=True)
class ConstitutionalRules:
    """НЕИЗМЕНЯЕМЫЕ ИНВАРИАНТЫ СИСТЕМЫ.

    Любое изменение — только через hard fork governance.
    """

    # 1. Decision Sovereignty
    single_decision_core: bool = True

    # 2. Запрет bypass side-effects
    side_effects_require_envelope: bool = True

    # 3. Детерминированность replay
    deterministic_replay: bool = True

    # 4. Запрет самоповреждающей эволюции
    evolution_must_be_safe: bool = True

    # 5. Governance подчинён DecisionCore
    governance_must_remain_subordinate: bool = True

    # 6. Абсолютный запрет второго мозга
    forbid_parallel_decision_brain: bool = True


class Constitution:
    """Runtime-проверка соблюдения законов."""

    def __init__(self, rules: ConstitutionalRules | None = None):
        self.rules = rules or ConstitutionalRules()
        self.version = int(CONSTITUTION_VERSION)

    # --- Decision sovereignty / side-effects gate ---
    def assert_decision_envelope(self, envelope: DecisionEnvelopeLike | None):
        if self.rules.side_effects_require_envelope and envelope is None:
            raise ConstitutionViolation("Side-effect without DecisionEnvelope")

    def assert_single_decision_core(self, *, is_single: bool) -> None:
        if self.rules.single_decision_core and not bool(is_single):
            raise ConstitutionViolation("Multiple decision cores detected")

    def assert_no_parallel_decision_brain(self, *, has_parallel_brain: bool) -> None:
        if self.rules.forbid_parallel_decision_brain and bool(has_parallel_brain):
            raise ConstitutionViolation("Parallel decision brain forbidden")

    def assert_governance_subordinate_to_decisioncore(self, *, subordinate: bool) -> None:
        if self.rules.governance_must_remain_subordinate and not bool(subordinate):
            raise ConstitutionViolation("Governance must remain subordinate to DecisionCore")

    # --- Deterministic replay ---
    def assert_replayable(self, deterministic: bool):
        if self.rules.deterministic_replay and not deterministic:
            raise ConstitutionViolation("Non-deterministic execution detected")

    # --- Safe evolution ---
    def assert_safe_evolution(self, is_safe: bool):
        if self.rules.evolution_must_be_safe and not is_safe:
            raise ConstitutionViolation("Unsafe evolution blocked")
