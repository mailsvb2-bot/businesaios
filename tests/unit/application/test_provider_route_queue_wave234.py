from __future__ import annotations

from types import SimpleNamespace

from application.business_autonomy.provider_admin_service import ProviderAdminService
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


def test_guarded_provider_approval_resume_replays_exact_approved_subject_after_fallback():
    for provider_key, channel_id, approved_payload in (
        ("slack_messaging", "C123", {"channel": "C123", "text": "hello"}),
        ("discord_messaging", "123", {"channel_id": "123", "text": "hello"}),
        ("email_connector", "user@example.org", {"recipient": "user@example.org", "subject": "Exact subject", "body": "hello"}),
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
                action="profit_sprint_onboarding_start@v1",
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


def test_legacy_provider_resume_still_rejects_non_send_message_archived_action():
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
                    },
                ),
            )

    envelope = SimpleNamespace(
        decision=SimpleNamespace(
            decision_id="dec-1",
            action="profit_sprint_onboarding_start@v1",
            payload={"tenant_id": "tenant-a", "business_id": "biz-a", "channel": "slack", "channel_id": "C123", "text": "hello"},
        )
    )
    handlers = ProviderAdminRouteHandlers(approval_store_factory=lambda: _Store(), decision_loader=lambda **_: envelope)

    try:
        handlers.resume_approved_message(tenant_id="tenant-a", approval_id="ap-1")
    except RuntimeError as exc:
        assert str(exc) == "provider_approval_resume_requires_send_message_v1"
    else:
        raise AssertionError("legacy approval without bound resume context must retain archive-action restriction")


def test_provider_approval_resume_finalizes_alert_dedup_only_after_verified_delivery():
    completed = []

    class _Store:
        def get(self, approval_id):
            return SimpleNamespace(status=SimpleNamespace(value='approved'), request=SimpleNamespace(approval_id=approval_id, tenant_id='tenant-a', subject_id='dec-1', metadata={'action_name': 'provider.slack_messaging.message_send', 'decision_id': 'dec-1', 'approval_resume_context': {'provider_key': 'slack_messaging', 'business_id': 'biz-a', 'operation': 'message_send', 'payload': {'channel': 'C1', 'text': 'hello'}}, 'approval_completion_context': {'dedup_key': 'dedup-1', 'reservation_id': 'res-1'}}))

    class _Service:
        def execute_queued_provider_sync(self, **kwargs):
            assert kwargs['approval_completion_context'] == {'dedup_key': 'dedup-1', 'reservation_id': 'res-1'}
            return {'result': {'accepted': True, 'status': 'live_executed', 'parsed_response': {'resource_id': 'msg-1'}}}

    envelope = SimpleNamespace(decision=SimpleNamespace(decision_id='dec-1', action='domain_action@v1', payload={'tenant_id': 'tenant-a'}))
    handlers = ProviderAdminRouteHandlers(service_factory=lambda **_: _Service(), approval_store_factory=lambda: _Store(), decision_loader=lambda **_: envelope, approval_completion_handler=lambda **kwargs: completed.append(kwargs))
    handlers.resume_approved_message(tenant_id='tenant-a', approval_id='ap-1')
    assert completed == [{'tenant_id': 'tenant-a', 'approval_id': 'ap-1', 'dedup_key': 'dedup-1', 'reservation_id': 'res-1', 'delivered': True, 'ambiguous': False}]


def test_email_approval_resume_keeps_dedup_fail_closed_when_smtp_only_accepted():
    completed = []

    class _Store:
        def get(self, approval_id):
            metadata = {'action_name': 'provider.email_connector.message_send', 'decision_id': 'dec-1', 'approval_resume_context': {'provider_key': 'email_connector', 'business_id': 'biz-a', 'operation': 'message_send', 'payload': {'recipient': 'user@example.org', 'subject': 'Exact subject', 'body': 'hello'}}, 'approval_completion_context': {'dedup_key': 'dedup-1', 'reservation_id': 'res-1'}}
            return SimpleNamespace(status=SimpleNamespace(value='approved'), request=SimpleNamespace(approval_id=approval_id, tenant_id='tenant-a', subject_id='dec-1', metadata=metadata))

    class _Service:
        def execute_queued_provider_sync(self, **kwargs):
            return {'result': {'accepted': True, 'status': 'live_executed', 'parsed_response': {'resource_id': '<message-id>', 'delivery_state': 'accepted'}, 'transport_response': {'smtp': {'accepted': True, 'delivered': False}}}}

    envelope = SimpleNamespace(decision=SimpleNamespace(decision_id='dec-1', action='domain_action@v1', payload={'tenant_id': 'tenant-a'}))
    handlers = ProviderAdminRouteHandlers(service_factory=lambda **_: _Service(), approval_store_factory=lambda: _Store(), decision_loader=lambda **_: envelope, approval_completion_handler=lambda **kwargs: completed.append(kwargs))
    handlers.resume_approved_message(tenant_id='tenant-a', approval_id='ap-1')
    assert completed == [{'tenant_id': 'tenant-a', 'approval_id': 'ap-1', 'dedup_key': 'dedup-1', 'reservation_id': 'res-1', 'delivered': False, 'ambiguous': True}]


def test_provider_approval_resume_releases_alert_dedup_after_terminal_non_delivery():
    completed = []

    class _Store:
        def get(self, approval_id):
            return SimpleNamespace(status=SimpleNamespace(value='approved'), request=SimpleNamespace(approval_id=approval_id, tenant_id='tenant-a', subject_id='dec-1', metadata={'action_name': 'provider.slack_messaging.message_send', 'decision_id': 'dec-1', 'approval_resume_context': {'provider_key': 'slack_messaging', 'business_id': 'biz-a', 'operation': 'message_send', 'payload': {'channel': 'C1', 'text': 'hello'}}, 'approval_completion_context': {'dedup_key': 'dedup-1', 'reservation_id': 'res-1'}}))

    class _Service:
        def execute_queued_provider_sync(self, **kwargs):
            return {'result': {'accepted': False, 'status': 'live_execution_failed', 'parsed_response': {'error_code': 'invalid_auth'}, 'error': {'category': 'provider_rejected'}}}

    envelope = SimpleNamespace(decision=SimpleNamespace(decision_id='dec-1', action='domain_action@v1', payload={'tenant_id': 'tenant-a'}))
    handlers = ProviderAdminRouteHandlers(service_factory=lambda **_: _Service(), approval_store_factory=lambda: _Store(), decision_loader=lambda **_: envelope, approval_completion_handler=lambda **kwargs: completed.append(kwargs))
    handlers.resume_approved_message(tenant_id='tenant-a', approval_id='ap-1')
    assert completed == [{'tenant_id': 'tenant-a', 'approval_id': 'ap-1', 'dedup_key': 'dedup-1', 'reservation_id': 'res-1', 'delivered': False, 'ambiguous': False}]



def test_provider_approval_resume_persists_ambiguous_alert_for_receiptless_transport_timeout():
    completed = []

    class _Store:
        def get(self, approval_id):
            metadata = {'action_name': 'provider.slack_messaging.message_send', 'decision_id': 'dec-1', 'approval_resume_context': {'provider_key': 'slack_messaging', 'business_id': 'biz-a', 'operation': 'message_send', 'payload': {'channel': 'C1', 'text': 'hello'}}, 'approval_completion_context': {'dedup_key': 'dedup-1', 'reservation_id': 'res-1'}}
            return SimpleNamespace(status=SimpleNamespace(value='approved'), request=SimpleNamespace(approval_id=approval_id, tenant_id='tenant-a', subject_id='dec-1', metadata=metadata))

    class _Service:
        def execute_queued_provider_sync(self, **kwargs):
            return {'result': {'accepted': False, 'status': 'live_execution_failed', 'error': {'category': 'transport_timeout', 'code': 'transport_timeout', 'retryable': True}}}

    envelope = SimpleNamespace(decision=SimpleNamespace(decision_id='dec-1', action='domain_action@v1', payload={'tenant_id': 'tenant-a'}))
    handlers = ProviderAdminRouteHandlers(service_factory=lambda **_: _Service(), approval_store_factory=lambda: _Store(), decision_loader=lambda **_: envelope, approval_completion_handler=lambda **kwargs: completed.append(kwargs))
    handlers.resume_approved_message(tenant_id='tenant-a', approval_id='ap-1')
    assert completed == [{'tenant_id': 'tenant-a', 'approval_id': 'ap-1', 'dedup_key': 'dedup-1', 'reservation_id': 'res-1', 'delivered': False, 'ambiguous': True}]


def test_provider_approval_resume_persists_ambiguous_alert_for_receiptless_queue_failure():
    completed = []

    class _Store:
        def get(self, approval_id):
            metadata = {'action_name': 'provider.slack_messaging.message_send', 'decision_id': 'dec-1', 'approval_resume_context': {'provider_key': 'slack_messaging', 'business_id': 'biz-a', 'operation': 'message_send', 'payload': {'channel': 'C1', 'text': 'hello'}}, 'approval_completion_context': {'dedup_key': 'dedup-1', 'reservation_id': 'res-1'}}
            return SimpleNamespace(status=SimpleNamespace(value='approved'), request=SimpleNamespace(approval_id=approval_id, tenant_id='tenant-a', subject_id='dec-1', metadata=metadata))

    class _Service:
        def execute_queued_provider_sync(self, **kwargs):
            return {'result': {'accepted': False, 'status': 'provider_queue_failed_without_history', 'error': {'category': 'provider_queue_failed'}}}

    envelope = SimpleNamespace(decision=SimpleNamespace(decision_id='dec-1', action='domain_action@v1', payload={'tenant_id': 'tenant-a'}))
    handlers = ProviderAdminRouteHandlers(service_factory=lambda **_: _Service(), approval_store_factory=lambda: _Store(), decision_loader=lambda **_: envelope, approval_completion_handler=lambda **kwargs: completed.append(kwargs))
    handlers.resume_approved_message(tenant_id='tenant-a', approval_id='ap-1')
    assert completed == [{'tenant_id': 'tenant-a', 'approval_id': 'ap-1', 'dedup_key': 'dedup-1', 'reservation_id': 'res-1', 'delivered': False, 'ambiguous': True}]


def test_receiptless_terminal_queue_state_is_ambiguous():
    result = ProviderAdminService._terminal_queue_result({'metadata': {'job_state': 'failed', 'job_last_error': 'RuntimeError:bookkeeping failed after transport', 'job_attempts': 1, 'job_max_attempts': 1}})
    assert result is not None
    assert result['status'] == 'ambiguous_delivery'
    assert result['error']['category'] == 'ambiguous_delivery'

def test_provider_approval_resume_persists_ambiguous_alert_on_ambiguous_delivery():
    completed = []

    class _Store:
        def get(self, approval_id):
            metadata = {'action_name': 'provider.slack_messaging.message_send', 'decision_id': 'dec-1', 'approval_resume_context': {'provider_key': 'slack_messaging', 'business_id': 'biz-a', 'operation': 'message_send', 'payload': {'channel': 'C1', 'text': 'hello'}}, 'approval_completion_context': {'dedup_key': 'dedup-1', 'reservation_id': 'res-1'}}
            return SimpleNamespace(status=SimpleNamespace(value='approved'), request=SimpleNamespace(approval_id=approval_id, tenant_id='tenant-a', subject_id='dec-1', metadata=metadata))

    class _Service:
        def execute_queued_provider_sync(self, **kwargs):
            return {'result': {'accepted': False, 'status': 'ambiguous_delivery', 'error': {'category': 'ambiguous_delivery'}}}

    envelope = SimpleNamespace(decision=SimpleNamespace(decision_id='dec-1', action='domain_action@v1', payload={'tenant_id': 'tenant-a'}))
    handlers = ProviderAdminRouteHandlers(service_factory=lambda **_: _Service(), approval_store_factory=lambda: _Store(), decision_loader=lambda **_: envelope, approval_completion_handler=lambda **kwargs: completed.append(kwargs))
    handlers.resume_approved_message(tenant_id='tenant-a', approval_id='ap-1')
    assert completed == [{'tenant_id': 'tenant-a', 'approval_id': 'ap-1', 'dedup_key': 'dedup-1', 'reservation_id': 'res-1', 'delivered': False, 'ambiguous': True}]
