from growth.core.growth_engine import GrowthEngine


class OpportunityPipeline:
    def __init__(self, growth_engine: GrowthEngine) -> None:
        self._growth_engine = growth_engine

    def run(self, signals: list[dict]) -> list[object]:
        return self._growth_engine.assemble_opportunities(signals)
