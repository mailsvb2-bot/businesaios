from runtime.bootstrap import build_crm_service


class _Action:
    action_type = 'crm_upsert_contact'


def test_runtime_crm_service_keeps_single_connector_registry() -> None:
    service = build_crm_service()
    first = service.connector_for('hubspot')
    second = service.connector_for('hubspot')
    assert first is second
