from typing import Protocol


class OpportunityRunPort(Protocol):
    def run(self, signals: list[dict]) -> list[object]: ...


class SignalToOpportunityFlow:
    def run(self, signals: list[dict], opportunity_pipeline: OpportunityRunPort) -> list[object]:
        return opportunity_pipeline.run(signals)
