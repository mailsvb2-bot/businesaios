from registry.base_registry import BaseRegistry
class BusinessStateFeedRegistry(BaseRegistry):
    def __init__(self) -> None: super().__init__(kind="business_state_feed")
    def register(self, name: str, item: object) -> None: self.register_unique(name, item, error_prefix="business_state_feed")
