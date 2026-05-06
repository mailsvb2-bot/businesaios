from canon.runtime_capability_rules import CAPABILITY_TO_ALLOWED_SERVICES
from runtime.capabilities import RuntimeCapability
from runtime.service_names import RuntimeServiceName


def test_decision_capability_surface_is_minimal() -> None:
    actual = set(CAPABILITY_TO_ALLOWED_SERVICES[RuntimeCapability.DECISION_EXECUTION])
    expected = {
        RuntimeServiceName.GOVERNANCE_CHAIN,
        RuntimeServiceName.ACTION_EXECUTOR,
    }
    assert actual == expected
