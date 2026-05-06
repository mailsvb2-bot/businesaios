from runtime.boot.web.runtime_web_services import RuntimeWebServices


class _Reader:
    pass


def test_runtime_web_services_exposes_canonical_infra_aliases():
    services = RuntimeWebServices(
        project_root='.',
        settings_gateway='gateway',
        messaging_policy_read_service=_Reader(),
        messaging_policy_event_store='store',
    )
    assert services.settings_store == 'gateway'
    assert services.messaging_policy_reader is services.messaging_policy_read_service
    assert services.messaging_policy_store == 'store'
