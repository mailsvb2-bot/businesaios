from __future__ import annotations

from types import SimpleNamespace

from application.business_autonomy.provider_catalog import provider_map
from entrypoints.api.approval_route_support import resume_hint
from entrypoints.api.provider_admin_route_handlers import ProviderAdminRouteHandlers


def test_provider_route_handlers_have_queue_methods():
    handlers = ProviderAdminRouteHandlers()
    assert callable(getattr(handlers, 'enqueue_provider_sync'))
    assert callable(getattr(handlers, 'tick_provider_sync_queue'))
    assert callable(getattr(handlers, 'describe_provider_live_client'))


def test_provider_approval_resume_uses_archived_send_message_only():
    class _Store:
        def get(self, approval_id):
            return SimpleNamespace(status=SimpleNamespace(value='approved'), request=SimpleNamespace(approval_id=approval_id, tenant_id='tenant-a', subject_id='dec-1', metadata={'action_name': 'provider.vk_messaging.message_send', 'decision_id': 'dec-1'}))

    class _Registry:
        def get(self, key):
            return provider_map()[key]

    class _Service:
        provider_registry = _Registry()
        def __init__(self):
            self.calls = []
        def execute_queued_provider_sync(self, **kwargs):
            self.calls.append(kwargs)
            return {'dispatch': {'queued': True, 'job_id': 'job-1'}, 'worker': {'succeeded': 1}, 'result': {'accepted': True, 'status': 'live_executed', 'parsed_response': {'resource_id': '77'}}}

    service = _Service()
    envelope = SimpleNamespace(decision=SimpleNamespace(decision_id='dec-1', action='send_message@v1', payload={'tenant_id': 'tenant-a', 'business_id': 'biz-a', 'channel': 'vk', 'user_id': '42', 'text': 'hello'}))
    handlers = ProviderAdminRouteHandlers(service_factory=lambda **_: service, approval_store_factory=lambda: _Store(), decision_loader=lambda **_: envelope)
    result = handlers.resume_approved_message(tenant_id='tenant-a', approval_id='ap-1')
    assert result['provider_key'] == 'vk_messaging' and result['business_id'] == 'biz-a'
    call = service.calls[0]
    assert call['payload']['peer_id'] == '42' and call['payload']['message'] == 'hello'
    assert call['payload']['_approval'] == {'decision_id': 'dec-1', 'execution_id': 'dec-1', 'approval_id': 'ap-1'}


def test_slack_discord_approval_resume_replays_exact_approved_subject_after_fallback():
    for provider_key, channel_id, approved_payload in (
        ("slack_messaging", "C123", {"channel": "C123", "text": "hello"}),
        ("discord_messaging", "123", {"channel_id": "123", "text": "hello"}),
    ):
        action_name = f"provider.{provider_key}.message_send"
        hint = resume_hint({"status": "approved", "action_name": action_name, "approval_id": "ap-1", "subject_id": "dec-1", "decision_id": "dec-1"})
        assert hint["resume_ready"] is True
        assert hint["resume_action"] == "/control-plane/provider-runtime/approval-resume"

        class _Store:
            def get(self, approval_id):
                return SimpleNamespace(
                    status=SimpleNamespace(value="approved"),
                    request=SimpleNamespace(
                        approval_id=approval_id,
                        tenant_id="tenant-a",
                        subject_id="dec-1",
                        metadata={
                            "action_name": action_name,
                            "decision_id": "dec-1",
                            "approval_resume_context": {
                                "provider_key": provider_key,
                                "business_id": "biz-approved",
                                "operation": "message_send",
                                "payload": approved_payload,
                            },
                        },
                    ),
                )

        class _Registry:
            def get(self, key):
                return provider_map()[key]

        class _Service:
            provider_registry = _Registry()
            def __init__(self):
                self.calls = []
            def execute_queued_provider_sync(self, **kwargs):
                self.calls.append(kwargs)
                return {"dispatch": {"queued": True, "job_id": "job-1"}, "worker": {"succeeded": 1}, "result": {"accepted": True, "status": "live_executed", "parsed_response": {"resource_id": "77"}}}

        service = _Service()
        envelope = SimpleNamespace(
            decision=SimpleNamespace(
                decision_id="dec-1",
                action="send_message@v1",
                payload={
                    "tenant_id": "tenant-a",
                    "business_id": "biz-archive",
                    "channel": "whatsapp",
                    "user_id": channel_id,
                    "text": "hello",
                },
            )
        )
        handlers = ProviderAdminRouteHandlers(service_factory=lambda **_: service, approval_store_factory=lambda: _Store(), decision_loader=lambda **_: envelope)
        result = handlers.resume_approved_message(tenant_id="tenant-a", approval_id="ap-1")
        assert result["provider_key"] == provider_key
        assert result["business_id"] == "biz-approved"
        sent = service.calls[0]["payload"]
        assert {key: value for key, value in sent.items() if key != "_approval"} == approved_payload
        assert sent["_approval"] == {"decision_id": "dec-1", "execution_id": "dec-1", "approval_id": "ap-1"}


def test_native_approval_resume_rejects_tampered_stored_provider_identity():
    class _Store:
        def get(self, approval_id):
            return SimpleNamespace(
                status=SimpleNamespace(value="approved"),
                request=SimpleNamespace(
                    approval_id=approval_id,
                    tenant_id="tenant-a",
                    subject_id="dec-1",
                    metadata={
                        "action_name": "provider.slack_messaging.message_send",
                        "decision_id": "dec-1",
                        "approval_resume_context": {
                            "provider_key": "discord_messaging",
                            "business_id": "biz-a",
                            "operation": "message_send",
                            "payload": {"channel": "C123", "text": "hello"},
                        },
                    },
                ),
            )

    envelope = SimpleNamespace(
        decision=SimpleNamespace(
            decision_id="dec-1",
            action="send_message@v1",
            payload={"tenant_id": "tenant-a", "channel": "slack", "user_id": "C123", "text": "hello"},
        )
    )
    handlers = ProviderAdminRouteHandlers(approval_store_factory=lambda: _Store(), decision_loader=lambda **_: envelope)

    try:
        handlers.resume_approved_message(tenant_id="tenant-a", approval_id="ap-1")
    except RuntimeError as exc:
        assert str(exc) == "provider_approval_resume_provider_mismatch"
    else:
        raise AssertionError("tampered provider resume context must fail closed")
