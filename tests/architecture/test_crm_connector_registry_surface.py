from runtime.bootstrap import build_crm_connector_registry


def test_runtime_bootstrap_exposes_connector_registry() -> None:
    registry = build_crm_connector_registry()
    assert registry.keys() == ('hubspot', 'pipedrive')
