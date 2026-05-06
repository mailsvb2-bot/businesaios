from registry.base_registry import BaseRegistry
class RoutingPolicyRegistry(BaseRegistry):
    def __init__(self) -> None: super().__init__(kind="routing_policy")
    def register(self, name: str, item: object) -> None: self.register_unique(name, item, error_prefix="routing_policy")
