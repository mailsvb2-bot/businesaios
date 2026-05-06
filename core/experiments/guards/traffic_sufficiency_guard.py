from __future__ import annotations

from core.experiments.errors import TrafficSufficiencyViolation


class TrafficSufficiencyGuard:
    def ensure_sufficient_traffic(self, *, control_exposures: int, treatment_exposures: int, minimum_required_exposures: int) -> None:
        if control_exposures < minimum_required_exposures:
            raise TrafficSufficiencyViolation(
                "insufficient control traffic: "
                f"observed={control_exposures}, required={minimum_required_exposures}"
            )
        if treatment_exposures < minimum_required_exposures:
            raise TrafficSufficiencyViolation(
                "insufficient treatment traffic: "
                f"observed={treatment_exposures}, required={minimum_required_exposures}"
            )
