from pathlib import Path

from runtime.boot.web.observability_boot_plan import ObservabilityBootArgs


class DummyApp:
    pass


def test_observability_boot_args_capture_dependencies():
    args = ObservabilityBootArgs(
        app=DummyApp(),
        project_root=Path('.'),
        settings_gateway=object(),
        messaging_policy_event_store=object(),
        messaging_policy_read_service=object(),
    )
    assert args.project_root == Path('.')
    assert args.settings_gateway is not None
    assert args.messaging_policy_event_store is not None
    assert args.messaging_policy_read_service is not None
