from registry.base_registry import BaseRegistry


class MatchScorerRegistry(BaseRegistry):
    def __init__(self) -> None: super().__init__(kind="match_scorer")
    def register(self, name: str, item: object) -> None: self.register_unique(name, item, error_prefix="match_scorer")
