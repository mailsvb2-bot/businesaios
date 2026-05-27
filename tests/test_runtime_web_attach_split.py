from entrypoints.api.security_owner_bundle import ApiSecurityOwnerBundle
from runtime.boot.settings.messaging_settings_gateway import build_messaging_settings_gateway
from runtime.boot.web.runtime_web_attach import (
    RuntimeWebAttachmentState,
    attach_runtime_web_bundle,
    build_runtime_web_attachment_attrs,
    iter_runtime_web_targets,
)
from runtime.platform.event_store.memory_event_store import MemoryEventStore
from runtime.runtime_infra import RuntimeInfra


class _Executor:
    class _Effects:
        pass

    def __init__(self):
        self._effects = self._Effects()


class _ReadService:
    def get_snapshot(self, *, tenant_id: str, user_id: str, correlation_id: str):
        return None


def test_iter_runtime_web_targets_yields_executor_and_effects():
    executor = _Executor()
    targets = list(iter_runtime_web_targets(runtime_obj=executor))
    assert targets[0] is executor
    assert targets[1] is executor._effects


def test_build_runtime_web_attachment_attrs_contains_bundle_and_routed_values():
    gateway = build_messaging_settings_gateway(event_store=MemoryEventStore())
    bundle = attach_runtime_web_bundle(
        runtime_obj=_Executor(),
        project_root='.',
        settings_gateway=gateway,
        messaging_policy_read_service=_ReadService(),
        messaging_policy_event_store=MemoryEventStore(),
    )
    state = RuntimeWebAttachmentState(
        bundle=bundle,
        settings_gateway=gateway,
        messaging_policy_read_service=bundle.messaging_policy_read_service,
        messaging_policy_event_store=bundle.messaging_policy_event_store,
        routed=bundle.routed,
    )
    attrs = build_runtime_web_attachment_attrs(state=state)
    assert attrs['web_bundle'] is bundle
    assert attrs['settings_gateway'] is gateway
    assert 'messaging_policy_observability_nav_bundle' in attrs


def test_attach_runtime_web_bundle_still_attaches_expected_attrs():
    executor = _Executor()
    gateway = build_messaging_settings_gateway(event_store=MemoryEventStore())
    bundle = attach_runtime_web_bundle(
        runtime_obj=executor,
        project_root='.',
        settings_gateway=gateway,
        messaging_policy_read_service=_ReadService(),
        messaging_policy_event_store=MemoryEventStore(),
    )
    assert executor.web_bundle is bundle
    assert executor._effects.web_bundle is bundle
    assert executor.messaging_policy_read_service is not None
    assert executor.messaging_policy_observability_nav_bundle is not None


def test_attach_runtime_web_bundle_reuses_runtime_infra_security_owner_bundle(tmp_path):
    executor = _Executor()
    bundle = ApiSecurityOwnerBundle.default(audit_path=tmp_path / 'runtime_web_attach_security.jsonl')
    executor.runtime_infra = RuntimeInfra(api_security_owner_bundle=bundle)
    gateway = build_messaging_settings_gateway(event_store=MemoryEventStore())
    attach_runtime_web_bundle(
        runtime_obj=executor,
        project_root='.',
        settings_gateway=gateway,
        messaging_policy_read_service=_ReadService(),
        messaging_policy_event_store=MemoryEventStore(),
    )
    assert executor.api_security_owner_bundle is bundle
    assert executor._effects.api_security_owner_bundle is bundle
