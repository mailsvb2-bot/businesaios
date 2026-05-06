"""Experimentation package."""

from shared.kinded_payloads import build_kinded_payload

CANON_EXPERIMENTATION_PACKAGE_OWNER = True

class AbTest:
    def build(self, payload: dict) -> dict:
        return build_kinded_payload("ab_test", payload)

class AudienceTest:
    def build(self, payload: dict) -> dict:
        return build_kinded_payload("audience_test", payload)

class BudgetTest:
    def build(self, payload: dict) -> dict:
        return build_kinded_payload("budget_test", payload)

class ChannelTest:
    def build(self, payload: dict) -> dict:
        return build_kinded_payload("channel_test", payload)

class CreativeTest:
    def build(self, payload: dict) -> dict:
        return build_kinded_payload("creative_test", payload)

class Experiment:
    def build(self, payload: dict) -> dict:
        return build_kinded_payload("experiment", payload)

class ExperimentEvaluator:
    def evaluate(self, payload: dict) -> dict:
        return build_kinded_payload("experiment_result", payload)

class ExperimentGuardrails:
    def evaluate(self, payload: dict) -> dict:
        return build_kinded_payload("experiment_guardrails_result", payload)

class ExperimentRegistry:
    def register(self, payload: dict) -> dict:
        return build_kinded_payload("experiment_registry", payload)

class ExperimentScheduler:
    def schedule(self, payload: dict) -> dict:
        return build_kinded_payload("experiment_schedule", payload)

class LandingTest:
    def build(self, payload: dict) -> dict:
        return build_kinded_payload("landing_test", payload)

class LoserShutdownPolicy:
    def evaluate(self, payload: dict) -> dict:
        return build_kinded_payload("loser_shutdown", payload)

class WinnerPromotionPolicy:
    def evaluate(self, payload: dict) -> dict:
        return build_kinded_payload("winner_promotion", payload)

__all__ = [
    "CANON_EXPERIMENTATION_PACKAGE_OWNER",
    "AbTest",
    "AudienceTest",
    "BudgetTest",
    "ChannelTest",
    "CreativeTest",
    "Experiment",
    "ExperimentEvaluator",
    "ExperimentGuardrails",
    "ExperimentRegistry",
    "ExperimentScheduler",
    "LandingTest",
    "LoserShutdownPolicy",
    "WinnerPromotionPolicy",
]
