from runtime.bootstrap.runtime_builder import build_runtime
from runtime.runtime_policies import RuntimePolicies


def test_runtime_contains_required_services() -> None:
    registry, _ = build_runtime()
    policies = RuntimePolicies()

    for service_name in policies.required_services:
        assert registry.has(service_name), service_name
