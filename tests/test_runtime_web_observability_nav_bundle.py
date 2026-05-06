from runtime.boot.web.runtime_web_service_builders import build_runtime_web_routed_services


def test_runtime_web_service_builders_include_observability_nav_bundle():
    routed = build_runtime_web_routed_services(project_root='.', settings_gateway=None, messaging_policy_read_service=None, messaging_policy_event_store=None)
    assert routed.messaging_policy_observability_nav_bundle is not None
