from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .build import build_blueprint, decisioncore_advisory_payload
from .contracts import (
    AgentBlueprint,
    AutomationOpportunity,
    BuildRequest,
    ComparisonEvidence,
    DiscoveryPolicy,
    DiscoveryReport,
    InterventionProof,
    InterventionSpend,
    ProcessBaseline,
    ProcessObservation,
    ROIReport,
)
from .discovery import discover_processes
from .measure import measure_outcome


@dataclass(frozen=True)
class DiscoverBuildMeasureService:
    policy: DiscoveryPolicy = DiscoveryPolicy()

    def discover(self, observations: Sequence[ProcessObservation]) -> DiscoveryReport:
        return discover_processes(observations, policy=self.policy)

    def build(self, opportunity: AutomationOpportunity, request: BuildRequest) -> AgentBlueprint:
        return build_blueprint(opportunity, request)

    def decisioncore_payload(self, blueprint: AgentBlueprint) -> dict[str, object]:
        return decisioncore_advisory_payload(blueprint)

    def measure(
        self,
        *,
        blueprint: AgentBlueprint,
        baseline: ProcessBaseline,
        intervention: InterventionProof,
        after_observations: Sequence[ProcessObservation],
        spend: InterventionSpend,
        comparison: ComparisonEvidence | None = None,
    ) -> ROIReport:
        return measure_outcome(
            blueprint=blueprint,
            baseline=baseline,
            intervention=intervention,
            after_observations=after_observations,
            spend=spend,
            comparison=comparison,
            policy=self.policy,
        )
