from runtime.boot.settings.messaging_settings_gateway import build_messaging_settings_gateway
from runtime.boot.web.runtime_web_attach import (
    RuntimeWebAttachmentState,
    build_runtime_web_attach_bundle_attrs,
    build_runtime_web_attach_core_attrs,
    build_runtime_web_attach_service_attrs,
    build_runtime_web_attachment_attrs,
)
from runtime.boot.web.runtime_web_bundle import RuntimeWebBundle
from runtime.boot.web.runtime_web_routed_services import RuntimeWebRoutedServices
from runtime.boot.web.runtime_web_services import RuntimeWebServices
from runtime.platform.event_store.memory_event_store import MemoryEventStore


def test_runtime_web_attachment_attr_groups_merge_consistently():
    gateway = build_messaging_settings_gateway(event_store=MemoryEventStore())
    routed = RuntimeWebRoutedServices(
        messaging_preferences_bundle='prefs',
        messaging_policy_observability_nav_bundle='nav',
        messaging_policy_trace_search_service='trace-service',
    )
    bundle = RuntimeWebBundle(
        services=RuntimeWebServices(
            project_root='.',
            settings_gateway=gateway,
            messaging_policy_read_service='read-service',
            messaging_policy_event_store='event-store',
            routed=routed,
        )
    )
    state = RuntimeWebAttachmentState(
        bundle=bundle,
        settings_gateway=gateway,
        messaging_policy_read_service='read-service',
        messaging_policy_event_store='event-store',
        api_security_owner_bundle='security-bundle',
        routed=routed,
    )

    core = build_runtime_web_attach_core_attrs(state=state)
    services = build_runtime_web_attach_service_attrs(routed=routed)
    bundles = build_runtime_web_attach_bundle_attrs(routed=routed)
    merged = build_runtime_web_attachment_attrs(state=state)

    assert merged == {**core, **services, **bundles}
    assert merged['api_security_owner_bundle'] == 'security-bundle'
    assert merged['messaging_preferences_bundle'] == 'prefs'
    assert merged['messaging_policy_observability_nav_bundle'] == 'nav'
    assert merged['messaging_policy_trace_search_service'] == 'trace-service'
