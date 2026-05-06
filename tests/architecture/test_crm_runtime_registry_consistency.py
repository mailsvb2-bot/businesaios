from runtime.bootstrap import build_crm_connector_registry, build_crm_provider_registry
from crm.registry.crm_registry_consistency import assert_crm_registry_consistency


def test_runtime_crm_registries_match() -> None:
    assert_crm_registry_consistency(
        build_crm_provider_registry(),
        build_crm_connector_registry(),
    ) is None
