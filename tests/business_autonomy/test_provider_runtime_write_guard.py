from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import application.business_autonomy.provider_admin_service as provider_admin_module
from application.business_autonomy.provider_admin_contract import ProviderCredentialSubmission
from application.business_autonomy.provider_admin_service import ProviderAdminService
from application.business_autonomy.provider_catalog import provider_map
from application.business_autonomy.provider_runtime_contract import ProviderSyncRunResult
from execution.approval_execution_gate import ApprovalExecutionGate
from execution.approval_policy_engine import ApprovalPolicyEngine
from governance.approval_contract import ApprovalDecision, ApprovalOutcome
from governance.approval_store import InMemoryApprovalStore, build_default_approval_store
from governance.approval_workflow import ApprovalWorkflow
from governance.change_control_policy import ChangeControlPolicy
from governance.rbac_contract import RoleId
from reliability.idempotency_store import InMemoryIdempotencyStore
from runtime.business_autonomy.distributed_state import FileDistributedDocumentStore
from runtime.business_autonomy.provider_activation_store import FileProviderActivationStore
from runtime.business_autonomy.provider_live_sync_runtime import ProviderLiveSyncRuntime
from runtime.business_autonomy.provider_queue_execution import ProviderQueueExecutionRuntime
from runtime.business_autonomy.provider_runtime_write_guard import (
    PROVIDER_WRITE_BLOCK_STATUS,
    ProviderRuntimeWriteGuard,
)
from runtime.queue.job_contract import JobClaimExpiryPolicy, JobState, utc_now
from runtime.queue.job_store_sqlite import SqliteJobStore
from security.connector_secret_scope import ConnectorSecretScope
from security.secret_contract import SecretRef
from security.secret_vault import InMemorySecretVault


def test_write_guard_blocks_live_ads_write_without_truth_matrix_write_support() -> None:
    provider = provider_map()["google_ads"]
    decision = ProviderRuntimeWriteGuard().evaluate(provider=provider, operation="campaign_launch", mode="live")

    assert decision.allowed is False
    assert decision.status == PROVIDER_WRITE_BLOCK_STATUS
    assert decision.is_write_operation is True
    assert decision.reason == "write_supported_false_in_provider_truth_matrix"
    assert decision.metadata["truth_source"] == "application.business_autonomy.provider_truth_matrix"


def test_write_guard_allows_dry_run_write_preparation() -> None:
    provider = provider_map()["google_ads"]
    decision = ProviderRuntimeWriteGuard().evaluate(provider=provider, operation="campaign_launch", mode="dry_run")

    assert decision.allowed is True
    assert decision.status == "allowed_non_live_mode"
    assert decision.is_write_operation is True


def test_live_sync_runtime_blocks_live_write_before_health_or_transport_execution() -> None:
    provider = provider_map()["google_ads"]
    runtime = ProviderLiveSyncRuntime(secret_vault=InMemorySecretVault(), transports={})

    result = runtime.run(
        provider=provider,
        tenant_id="tenant-demo",
        business_id="business-demo",
        operation="campaign_launch",
        mode="live",
        payload={"budget": 100},
    )

    assert result.accepted is False
    assert result.status == PROVIDER_WRITE_BLOCK_STATUS
    guard = result.metadata["provider_write_guard"]
    assert guard["allowed"] is False
    assert guard["is_write_operation"] is True
    assert guard["metadata"]["truth"]["write_supported"] is False
    assert "health_probe" not in result.metadata
    assert "transport_response" not in result.metadata


def test_live_sync_runtime_still_allows_dry_run_write_envelope() -> None:
    provider = provider_map()["google_ads"]
    runtime = ProviderLiveSyncRuntime(secret_vault=InMemorySecretVault(), transports={})

    result = runtime.run(
        provider=provider,
        tenant_id="tenant-demo",
        business_id="business-demo",
        operation="campaign_launch",
        mode="dry_run",
        payload={"budget": 100},
    )

    assert result.accepted is False or result.status in {"dry_run_ready", "rejected_misconfigured"}
    assert result.metadata["provider_write_guard"]["status"] == "allowed_non_live_mode"


def test_queue_blocks_live_write_job_before_persistence(tmp_path: Path) -> None:
    provider = provider_map()["google_ads"]
    store = SqliteJobStore(tmp_path / "provider_jobs.sqlite3")
    queue = ProviderQueueExecutionRuntime(
        secret_vault=InMemorySecretVault(),
        live_runtime=ProviderLiveSyncRuntime(secret_vault=InMemorySecretVault(), transports={}),
        store=store,
    )

    result = queue.enqueue_sync(
        provider=provider,
        tenant_id="tenant-demo",
        business_id="business-demo",
        operation="campaign_launch",
        mode="live",
        payload={"budget": 100},
    )

    assert result.queued is False
    assert result.job_id == ""
    assert result.status == PROVIDER_WRITE_BLOCK_STATUS
    assert result.metadata["fail_closed_before_queue"] is True
    assert result.metadata["provider_write_guard"]["allowed"] is False
    assert queue.list_jobs(tenant_id="tenant-demo", business_id="business-demo", provider_key="google_ads") == ()


def test_queue_allows_dry_run_write_job() -> None:
    provider = provider_map()["google_ads"]
    queue = ProviderQueueExecutionRuntime(
        secret_vault=InMemorySecretVault(),
        live_runtime=ProviderLiveSyncRuntime(secret_vault=InMemorySecretVault(), transports={}),
    )

    result = queue.enqueue_sync(
        provider=provider,
        tenant_id="tenant-demo",
        business_id="business-demo",
        operation="campaign_launch",
        mode="dry_run",
        payload={"budget": 100},
    )

    assert result.queued is True
    assert result.status == "queued"
    assert result.metadata["provider_write_guard"]["status"] == "allowed_non_live_mode"


def _approved_native_guard(*, provider_key: str, business_id: str, message_payload: dict[str, object]):
    store = InMemoryApprovalStore()
    workflow = ApprovalWorkflow(store=store)
    gate = ApprovalExecutionGate(approval_policy_engine=ApprovalPolicyEngine(change_control_policy=ChangeControlPolicy()), approval_workflow=workflow)
    guard = ProviderRuntimeWriteGuard(approval_gate=gate, approval_store=store)
    provider = provider_map()[provider_key]
    approval = {'decision_id': f'dec-{provider_key}', 'execution_id': f'exec-{provider_key}'}
    payload = {**message_payload, '_approval': approval}
    denied = guard.evaluate(provider=provider, operation='message_send', mode='live', tenant_id='tenant-a', business_id=business_id, payload=payload)
    assert denied.allowed is False and denied.reason == 'approval_submitted_awaiting_operator'
    evidence = denied.metadata['approval']
    approval_id = str(evidence['approval_id'])
    record = workflow.get(approval_id)
    assert record is not None and record.request.metadata['approval_request_fingerprint']
    assert record.request.metadata['approval_resume_context'] == {
        'provider_key': provider_key,
        'business_id': business_id,
        'operation': 'message_send',
        'payload': message_payload,
    }
    workflow.evaluate(ApprovalDecision(approval_id=approval_id, tenant_id='tenant-a', actor_id='owner-approver', role_id=RoleId.OWNER, outcome=ApprovalOutcome.APPROVE, rationale='approved'))
    payload['_approval'] = {**approval, 'approval_id': approval_id}
    return provider, guard, payload


def test_native_messaging_live_write_requires_exact_approved_subject() -> None:
    for provider_key, business_id, message_payload in (
        ('vk_messaging', 'vk-biz', {'peer_id': 42, 'text': 'hello'}),
        ('max_messaging', 'max-biz', {'chat_id': 99, 'text': 'hello'}),
        ('slack_messaging', 'slack-biz', {'channel_id': 'C123', 'text': 'hello'}),
        ('discord_messaging', 'discord-biz', {'channel_id': '123', 'text': 'hello'}),
        ('instagram_messaging', 'instagram-biz', {'recipient_id': 'ig-user-1', 'text': 'hello'}),
        ('messenger_messaging', 'messenger-biz', {'recipient_id': 'psid-1', 'text': 'hello'}),
        ('email_connector', 'email-biz', {'recipient': 'user@example.org', 'subject': 'Subject', 'body': 'hello'}),
    ):
        provider, guard, payload = _approved_native_guard(provider_key=provider_key, business_id=business_id, message_payload=message_payload)
        allowed = guard.evaluate(provider=provider, operation='message_send', mode='live', tenant_id='tenant-a', business_id=business_id, payload=payload)
        assert allowed.allowed is True and allowed.reason == 'approval_satisfied'
        changed = {**payload, 'text': 'changed after approval'}
        rejected = guard.evaluate(provider=provider, operation='message_send', mode='live', tenant_id='tenant-a', business_id=business_id, payload=changed)
        assert rejected.allowed is False and rejected.reason == 'approval_subject_mismatch'


def test_native_messaging_live_write_truth_is_guarded_not_publicly_unconditional() -> None:
    for provider_key in ('vk_messaging', 'max_messaging', 'slack_messaging', 'discord_messaging', 'instagram_messaging', 'messenger_messaging', 'line_messaging', 'viber_messaging', 'email_connector'):
        provider = provider_map()[provider_key]
        denied = ProviderRuntimeWriteGuard().evaluate(provider=provider, operation='message_send', mode='live', tenant_id='tenant-a', business_id='biz-a', payload={'text': 'hello'})
        assert denied.allowed is False and denied.reason == 'approval_context_missing'
        assert denied.metadata['truth']['write_supported'] is True
        assert denied.metadata['truth']['approval_required'] is True


def test_approved_vk_write_requires_canonical_queue_before_transport() -> None:
    provider, guard, payload = _approved_native_guard(provider_key='vk_messaging', business_id='vk-biz', message_payload={'peer_id': 42, 'text': 'hello'})
    runtime = ProviderLiveSyncRuntime(secret_vault=InMemorySecretVault(), transports={'vk_messaging': object()}, write_guard=guard)
    result = runtime.run(provider=provider, tenant_id='tenant-a', business_id='vk-biz', operation='message_send', mode='live', payload=payload)
    assert result.accepted is False and result.status == 'rejected_provider_write_requires_queue'
    assert 'transport_response' not in result.metadata


def test_guarded_native_approved_write_requires_canonical_queue_before_transport() -> None:
    for provider_key, business_id, message_payload in (
        ('slack_messaging', 'slack-biz', {'channel_id': 'C123', 'text': 'hello'}),
        ('discord_messaging', 'discord-biz', {'channel_id': '123', 'text': 'hello'}),
        ('instagram_messaging', 'instagram-biz', {'recipient_id': 'ig-user-1', 'text': 'hello'}),
        ('messenger_messaging', 'messenger-biz', {'recipient_id': 'psid-1', 'text': 'hello'}),
        ('email_connector', 'email-biz', {'recipient': 'user@example.org', 'subject': 'Subject', 'body': 'hello'}),
    ):
        provider, guard, payload = _approved_native_guard(provider_key=provider_key, business_id=business_id, message_payload=message_payload)
        runtime = ProviderLiveSyncRuntime(secret_vault=InMemorySecretVault(), transports={provider_key: object()}, write_guard=guard)
        result = runtime.run(provider=provider, tenant_id='tenant-a', business_id=business_id, operation='message_send', mode='live', payload=payload)
        assert result.accepted is False and result.status == 'rejected_provider_write_requires_queue'
        assert 'transport_response' not in result.metadata


def test_slack_discord_approved_queue_execution_is_one_shot_and_replay_safe(tmp_path: Path) -> None:
    for provider_key, business_id, message_payload, response_body, resource_id in (
        ('slack_messaging', 'slack-biz', {'channel_id': 'C123', 'text': 'hello'}, '{"ok":true,"channel":"C123","ts":"1700.0001"}', '1700.0001'),
        ('discord_messaging', 'discord-biz', {'channel_id': '123', 'text': 'hello'}, '{"id":"999","channel_id":"123","content":"hello"}', '999'),
    ):
        provider, guard, payload = _approved_native_guard(provider_key=provider_key, business_id=business_id, message_payload=message_payload)
        vault = InMemorySecretVault()
        for name, value in (('webhook_secret', 'bridge-secret'), ('bot_token', 'bot-token')):
            vault.seed_plaintext(
                ref=SecretRef(tenant_id='tenant-a', connector_id=provider.connector_id, scope=business_id, secret_name=f'{provider.connector_id}.{name}'),
                plaintext=value,
            )
        class _Transport:
            def __init__(self):
                self.calls = []
            def execute(self, **kwargs):
                self.calls.append(kwargs)
                return {'http_status': 200, 'response_body': response_body}
        transport = _Transport()
        store = SqliteJobStore(tmp_path / f'{provider_key}.sqlite3')
        runtime = ProviderLiveSyncRuntime(vault, transports={provider_key: transport}, write_guard=guard)
        queue = ProviderQueueExecutionRuntime(vault, live_runtime=runtime, store=store, write_guard=guard, idempotency_store=InMemoryIdempotencyStore())
        first = queue.enqueue_sync(provider=provider, tenant_id='tenant-a', business_id=business_id, operation='message_send', mode='live', payload=payload)
        duplicate = queue.enqueue_sync(provider=provider, tenant_id='tenant-a', business_id=business_id, operation='message_send', mode='live', payload=payload)
        assert first.queued is True and duplicate.job_id == first.job_id and duplicate.status == 'dedupe_existing'
        assert store.get(tenant_id='tenant-a', job_id=first.job_id).max_attempts == 1
        report = queue.tick(provider_registry={provider_key: provider}, tenant_id='tenant-a', job_id=first.job_id)
        assert report['succeeded'] == 1 and len(transport.calls) == 1
        history = runtime.sync_history.list_for_provider(tenant_id='tenant-a', business_id=business_id, provider_key=provider_key, limit=10)
        assert history and history[0]['parsed_response']['resource_id'] == resource_id


def test_vk_approved_execution_is_one_shot_across_queue_replays_and_retention(tmp_path: Path) -> None:
    provider, guard, payload = _approved_native_guard(provider_key='vk_messaging', business_id='vk-biz', message_payload={'peer_id': 42, 'text': 'hello'})
    store = SqliteJobStore(tmp_path / 'provider-write.sqlite3')
    queue = ProviderQueueExecutionRuntime(secret_vault=InMemorySecretVault(), live_runtime=ProviderLiveSyncRuntime(InMemorySecretVault(), transports={}, write_guard=guard), store=store, write_guard=guard, idempotency_store=InMemoryIdempotencyStore())
    first = queue.enqueue_sync(provider=provider, tenant_id='tenant-a', business_id='vk-biz', operation='message_send', mode='live', payload=payload)
    second = queue.enqueue_sync(provider=provider, tenant_id='tenant-a', business_id='vk-biz', operation='message_send', mode='live', payload=payload)
    assert first.queued is True and second.job_id == first.job_id and second.status == 'dedupe_existing'
    stored = store.get(tenant_id='tenant-a', job_id=first.job_id)
    assert stored is not None and stored.max_attempts == 6
    assert stored.claim_expiry_policy is JobClaimExpiryPolicy.RETRY_IF_BUDGET
    store.mark_dead_letter(tenant_id='tenant-a', job_id=first.job_id, error='ambiguous_delivery')
    terminal_replay = queue.enqueue_sync(provider=provider, tenant_id='tenant-a', business_id='vk-biz', operation='message_send', mode='live', payload=payload)
    assert terminal_replay.job_id == first.job_id and terminal_replay.status == 'idempotency_replay'
    store.purge_terminal_jobs(tenant_id='tenant-a', queue_name='provider_sync', states=(JobState.DEAD_LETTER,), older_than=utc_now() + timedelta(seconds=1))
    purged_replay = queue.enqueue_sync(provider=provider, tenant_id='tenant-a', business_id='vk-biz', operation='message_send', mode='live', payload=payload)
    assert purged_replay.queued is False and purged_replay.job_id == '' and purged_replay.status == 'idempotency_rejected'


def test_vk_approval_queue_receipt_replay_is_at_most_once(tmp_path: Path, monkeypatch) -> None:
    class _Onboarding:
        def onboard(self, request):
            return type('OnboardingResult', (), {'persistent_surfaces': ('evidence',), 'ready': True})()

    class _FakeVkTransport:
        def __init__(self):
            self.calls = []
        def execute(self, **kwargs):
            self.calls.append(kwargs)
            return {'http_status': 200, 'response_body': '{"response":777}', 'parsed_response': {'provider_key': 'vk_messaging', 'operation': 'message_send', 'http_status': 200, 'ok': True, 'resource_id': '777', 'error_code': None, 'retryable': False, 'delivery_state': 'accepted'}, '_response_ok': True}

    monkeypatch.setenv('DATA_DIR', str(tmp_path / 'runtime'))
    monkeypatch.setenv('BUSINESAIOS_APPROVAL_STORE_BACKEND', 'memory')
    service = ProviderAdminService(onboarding_service=_Onboarding(), secret_vault=InMemorySecretVault(), connector_secret_scope=ConnectorSecretScope(), activation_store=FileProviderActivationStore(FileDistributedDocumentStore(tmp_path / 'docs')))
    service.activate_provider(ProviderCredentialSubmission(tenant_id='tenant-a', business_id='biz-a', provider_key='vk_messaging', ownership_key='owner:biz-a', requested_by='tester', external_ref='vk://biz-a', metadata={'verified_owner': True}, secrets={'webhook_secret': 'secret', 'access_token': 'token'}))
    transport = _FakeVkTransport()
    monkeypatch.setattr(provider_admin_module, 'build_provider_vendor_transports', lambda vault: {'vk_messaging': transport})
    base = {'peer_id': '42', 'random_id': 0, 'message': 'hello', 'group_id': '{group_id}', '_approval': {'decision_id': 'dec-1', 'execution_id': 'dec-1'}}
    first = service.execute_queued_provider_sync(tenant_id='tenant-a', business_id='biz-a', provider_key='vk_messaging', operation='message_send', mode='live', payload=base)
    approval_id = first['dispatch']['metadata']['provider_write_guard']['metadata']['approval']['approval_id']
    assert first['dispatch']['queued'] is False and transport.calls == []
    ApprovalWorkflow(store=build_default_approval_store()).evaluate(ApprovalDecision(approval_id=approval_id, tenant_id='tenant-a', actor_id='owner-2', role_id=RoleId.OWNER, outcome=ApprovalOutcome.APPROVE, rationale='approve exact VK send'))
    approved = {**base, '_approval': {**base['_approval'], 'approval_id': approval_id}}
    second = service.execute_queued_provider_sync(tenant_id='tenant-a', business_id='biz-a', provider_key='vk_messaging', operation='message_send', mode='live', payload=approved)
    third = service.execute_queued_provider_sync(tenant_id='tenant-a', business_id='biz-a', provider_key='vk_messaging', operation='message_send', mode='live', payload=approved)
    assert second['result']['status'] == 'live_executed' and second['result']['parsed_response']['resource_id'] == '777'
    assert third['result']['parsed_response']['resource_id'] == '777' and len(transport.calls) == 1


def test_caller_supplied_queue_markers_cannot_bypass_canonical_queue() -> None:
    provider, guard, payload = _approved_native_guard(provider_key="slack_messaging", business_id="slack-biz", message_payload={"channel_id": "C123", "text": "hello"})

    class _Transport:
        def execute(self, **_kwargs):
            raise AssertionError("forged queue provenance must not reach transport")

    runtime = ProviderLiveSyncRuntime(secret_vault=InMemorySecretVault(), transports={"slack_messaging": _Transport()}, write_guard=guard)
    result = runtime.run(
        provider=provider,
        tenant_id="tenant-a",
        business_id="slack-biz",
        operation="message_send",
        mode="live",
        payload={**payload, "_provider_queue_execution": True, "_provider_queue_job_id": "forged-job", "_provider_write_approved": True, "_allow_network": True},
    )
    assert result.accepted is False and result.status == "rejected_provider_write_requires_queue"
    request_payload = result.metadata["request_envelope"]["payload"]
    assert all(key not in request_payload for key in ("_provider_queue_execution", "_provider_queue_job_id", "_provider_write_approved", "_allow_network"))


def test_native_guard_persists_internal_completion_context_without_binding_it_to_replay_subject() -> None:
    store = InMemoryApprovalStore()
    workflow = ApprovalWorkflow(store=store)
    gate = ApprovalExecutionGate(approval_policy_engine=ApprovalPolicyEngine(change_control_policy=ChangeControlPolicy()), approval_workflow=workflow)
    guard = ProviderRuntimeWriteGuard(approval_gate=gate, approval_store=store)
    provider = provider_map()['slack_messaging']
    payload = {'channel_id': 'C123', 'text': 'hello', '_approval': {'decision_id': 'dec-slack', 'execution_id': 'exec-slack'}}
    completion = {'dedup_key': 'tenant-a|biz-a|ceo|slack|a1|u1', 'reservation_id': 'res-1'}
    denied = guard.evaluate(provider=provider, operation='message_send', mode='live', tenant_id='tenant-a', business_id='biz-a', payload=payload, approval_completion_context=completion)
    approval_id = str(denied.metadata['approval']['approval_id'])
    record = workflow.get(approval_id)
    assert record is not None and record.request.metadata['approval_completion_context'] == completion
    completion['dedup_key'] = 'mutated-after-submit'
    assert record.request.metadata['approval_completion_context']['dedup_key'].startswith('tenant-a|biz-a|')
    workflow.evaluate(ApprovalDecision(approval_id=approval_id, tenant_id='tenant-a', actor_id='owner-approver', role_id=RoleId.OWNER, outcome=ApprovalOutcome.APPROVE, rationale='approved'))
    replay_payload = {**payload, '_approval': {**payload['_approval'], 'approval_id': approval_id}}
    allowed = guard.evaluate(provider=provider, operation='message_send', mode='live', tenant_id='tenant-a', business_id='biz-a', payload=replay_payload)
    assert allowed.allowed is True and allowed.reason == 'approval_satisfied'


def test_native_approval_completion_context_is_fingerprint_bound_across_resume() -> None:
    store = InMemoryApprovalStore()
    workflow = ApprovalWorkflow(store=store)
    gate = ApprovalExecutionGate(approval_policy_engine=ApprovalPolicyEngine(change_control_policy=ChangeControlPolicy()), approval_workflow=workflow)
    guard = ProviderRuntimeWriteGuard(approval_gate=gate, approval_store=store)
    provider = provider_map()['slack_messaging']
    completion = {'dedup_key': 'dedup-1', 'reservation_id': 'res-1'}
    payload = {'channel_id': 'C123', 'text': 'hello', '_approval': {'decision_id': 'dec-alert', 'execution_id': 'exec-alert'}}
    denied = guard.evaluate(provider=provider, operation='message_send', mode='live', tenant_id='tenant-a', business_id='biz-a', payload=payload, approval_completion_context=completion)
    approval_id = str(denied.metadata['approval']['approval_id'])
    workflow.evaluate(ApprovalDecision(approval_id=approval_id, tenant_id='tenant-a', actor_id='owner-approver', role_id=RoleId.OWNER, outcome=ApprovalOutcome.APPROVE, rationale='approve alert'))
    approved = {**payload, '_approval': {**payload['_approval'], 'approval_id': approval_id}}
    allowed = guard.evaluate(provider=provider, operation='message_send', mode='live', tenant_id='tenant-a', business_id='biz-a', payload=approved, approval_completion_context=completion)
    missing_context = guard.evaluate(provider=provider, operation='message_send', mode='live', tenant_id='tenant-a', business_id='biz-a', payload=approved)
    record = workflow.get(approval_id)
    assert record is not None and record.request.metadata['approval_completion_context'] == completion
    assert allowed.allowed is True and allowed.reason == 'approval_satisfied'
    assert missing_context.allowed is True
    assert missing_context.metadata['approval']['subject_fingerprint'] == allowed.metadata['approval']['subject_fingerprint']


class _ProviderResultRuntime:
    def __init__(self, result: ProviderSyncRunResult) -> None:
        self.result = result
        self.calls: list[dict[str, object]] = []

    def run(self, **kwargs):
        self.calls.append(kwargs)
        return self.result



def test_email_pre_send_transport_failure_can_retry_without_crossing_smtp_boundary(tmp_path: Path) -> None:
    provider, guard, payload = _approved_native_guard(
        provider_key='email_connector',
        business_id='email-biz',
        message_payload={'recipient': 'user@example.org', 'subject': 'Subject', 'body': 'hello'},
    )
    runtime = _ProviderResultRuntime(
        ProviderSyncRunResult(
            provider_key='email_connector', operation='message_send', mode='live',
            status='live_execution_failed', accepted=False,
            metadata={
                'parsed_response': {
                    'delivery_state': 'not_attempted', 'error_category': 'transport',
                    'error_code': 'smtp_pre_send_transport_failure', 'retryable': True,
                },
                'retry_policy': {'category': 'transport', 'retryable': True, 'next_delay_seconds': 20, 'max_attempts': 6},
            },
        )
    )
    store = SqliteJobStore(tmp_path / 'email-pre-send.sqlite3')
    queue = ProviderQueueExecutionRuntime(
        InMemorySecretVault(), live_runtime=runtime, store=store, write_guard=guard,
        idempotency_store=InMemoryIdempotencyStore(),
    )
    dispatched = queue.enqueue_sync(
        provider=provider, tenant_id='tenant-a', business_id='email-biz',
        operation='message_send', mode='live', payload=payload,
    )
    queued = store.get(tenant_id='tenant-a', job_id=dispatched.job_id)
    assert queued is not None and queued.claim_expiry_policy is JobClaimExpiryPolicy.DEAD_LETTER_AMBIGUOUS
    report = queue.tick(provider_registry={'email_connector': provider}, tenant_id='tenant-a', job_id=dispatched.job_id)
    retried = store.get(tenant_id='tenant-a', job_id=dispatched.job_id)
    assert report['retried'] == 1 and report['dead_lettered'] == 0
    assert retried is not None and retried.state is JobState.PENDING
    assert retried.claim_expiry_policy is JobClaimExpiryPolicy.RETRY_IF_BUDGET


def test_email_nonretryable_pre_send_failure_is_not_misclassified_as_ambiguous(tmp_path: Path) -> None:
    provider, guard, payload = _approved_native_guard(
        provider_key='email_connector',
        business_id='email-biz',
        message_payload={'recipient': 'bad-address', 'subject': 'Subject', 'body': 'hello'},
    )
    runtime = _ProviderResultRuntime(
        ProviderSyncRunResult(
            provider_key='email_connector', operation='message_send', mode='live',
            status='live_execution_failed', accepted=False,
            metadata={
                'parsed_response': {
                    'delivery_state': 'not_attempted', 'error_category': 'validation',
                    'error_code': 'email address is invalid', 'retryable': False,
                },
                'retry_policy': {'category': 'validation', 'retryable': False, 'next_delay_seconds': None, 'max_attempts': 1},
            },
        )
    )
    store = SqliteJobStore(tmp_path / 'email-validation.sqlite3')
    queue = ProviderQueueExecutionRuntime(
        InMemorySecretVault(), live_runtime=runtime, store=store, write_guard=guard,
        idempotency_store=InMemoryIdempotencyStore(),
    )
    dispatched = queue.enqueue_sync(
        provider=provider, tenant_id='tenant-a', business_id='email-biz',
        operation='message_send', mode='live', payload=payload,
    )
    report = queue.tick(provider_registry={'email_connector': provider}, tenant_id='tenant-a', job_id=dispatched.job_id)
    terminal = store.get(tenant_id='tenant-a', job_id=dispatched.job_id)
    assert report['dead_lettered'] == 1 and report['retried'] == 0
    assert terminal is not None and terminal.state is JobState.DEAD_LETTER
    assert 'validation' in str(terminal.last_error).lower()
    assert 'ambiguous_delivery' not in str(terminal.last_error)


def test_email_safe_retry_rearms_ambiguous_claim_policy_before_next_smtp_attempt(tmp_path: Path) -> None:
    provider, guard, payload = _approved_native_guard(
        provider_key='email_connector',
        business_id='email-biz',
        message_payload={'recipient': 'user@example.org', 'subject': 'Subject', 'body': 'hello'},
    )
    store = SqliteJobStore(tmp_path / 'email-rearm.sqlite3')

    class _Runtime:
        def __init__(self):
            self.calls = 0
            self.second_attempt_policy = None

        def run(self, **kwargs):
            self.calls += 1
            if self.calls == 1:
                return ProviderSyncRunResult(
                    provider_key='email_connector', operation='message_send', mode='live',
                    status='live_execution_failed', accepted=False,
                    metadata={
                        'parsed_response': {'delivery_state': 'not_attempted', 'error_category': 'transport', 'error_code': 'smtp_pre_send_transport_failure', 'retryable': True},
                        'retry_policy': {'category': 'transport', 'retryable': True, 'next_delay_seconds': 0, 'max_attempts': 6},
                    },
                )
            current = store.get(tenant_id=kwargs['tenant_id'], job_id=kwargs['_queue_job_id'])
            self.second_attempt_policy = current.claim_expiry_policy if current is not None else None
            return ProviderSyncRunResult(
                provider_key='email_connector', operation='message_send', mode='live',
                status='live_executed', accepted=True, metadata={},
            )

    runtime = _Runtime()
    queue = ProviderQueueExecutionRuntime(
        InMemorySecretVault(), live_runtime=runtime, store=store, write_guard=guard,
        idempotency_store=InMemoryIdempotencyStore(),
    )
    dispatched = queue.enqueue_sync(
        provider=provider, tenant_id='tenant-a', business_id='email-biz',
        operation='message_send', mode='live', payload=payload,
    )
    first = queue.tick(provider_registry={'email_connector': provider}, tenant_id='tenant-a', job_id=dispatched.job_id)
    pending = store.get(tenant_id='tenant-a', job_id=dispatched.job_id)
    assert first['retried'] == 1 and pending is not None and pending.state is JobState.PENDING
    assert pending.claim_expiry_policy is JobClaimExpiryPolicy.RETRY_IF_BUDGET

    second = queue.tick(provider_registry={'email_connector': provider}, tenant_id='tenant-a', job_id=dispatched.job_id)
    assert second['succeeded'] == 1
    assert runtime.second_attempt_policy is JobClaimExpiryPolicy.DEAD_LETTER_AMBIGUOUS


def test_email_ambiguous_smtp_send_is_dead_lettered_and_never_replayed(tmp_path: Path) -> None:
    provider, guard, payload = _approved_native_guard(
        provider_key='email_connector',
        business_id='email-biz',
        message_payload={'recipient': 'user@example.org', 'subject': 'Subject', 'body': 'hello'},
    )
    runtime = _ProviderResultRuntime(
        ProviderSyncRunResult(
            provider_key='email_connector', operation='message_send', mode='live',
            status='live_execution_failed', accepted=False,
            metadata={
                'parsed_response': {
                    'delivery_state': 'unknown', 'error_category': 'ambiguous_delivery',
                    'error_code': None, 'retryable': False,
                },
                'retry_policy': {'category': 'ambiguous_delivery', 'retryable': False, 'next_delay_seconds': None, 'max_attempts': 1},
            },
        )
    )
    store = SqliteJobStore(tmp_path / 'email-ambiguous.sqlite3')
    queue = ProviderQueueExecutionRuntime(
        InMemorySecretVault(), live_runtime=runtime, store=store, write_guard=guard,
        idempotency_store=InMemoryIdempotencyStore(),
    )
    dispatched = queue.enqueue_sync(
        provider=provider, tenant_id='tenant-a', business_id='email-biz',
        operation='message_send', mode='live', payload=payload,
    )
    report = queue.tick(provider_registry={'email_connector': provider}, tenant_id='tenant-a', job_id=dispatched.job_id)
    terminal = store.get(tenant_id='tenant-a', job_id=dispatched.job_id)
    assert report['dead_lettered'] == 1 and report['retried'] == 0
    assert terminal is not None and terminal.state is JobState.DEAD_LETTER
    assert 'ambiguous_delivery' in str(terminal.last_error)

def test_max_guarded_429_retries_same_canonical_job_without_relaxing_claim_expiry(tmp_path: Path) -> None:
    provider, guard, payload = _approved_native_guard(
        provider_key='max_messaging',
        business_id='max-biz',
        message_payload={'chat_id': '99', 'text': 'hello'},
    )
    runtime = _ProviderResultRuntime(
        ProviderSyncRunResult(
            provider_key='max_messaging',
            operation='message_send',
            mode='live',
            status='live_execution_failed',
            accepted=False,
            metadata={
                'parsed_response': {
                    'http_status': 429,
                    'delivery_state': 'rejected',
                    'error_category': 'rate_limit',
                    'retryable': True,
                },
                'retry_policy': {
                    'category': 'rate_limit',
                    'retryable': True,
                    'next_delay_seconds': 37,
                    'max_attempts': 6,
                },
            },
        )
    )
    store = SqliteJobStore(tmp_path / 'max-rate-limit.sqlite3')
    queue = ProviderQueueExecutionRuntime(
        InMemorySecretVault(),
        live_runtime=runtime,
        store=store,
        write_guard=guard,
        idempotency_store=InMemoryIdempotencyStore(),
    )
    dispatched = queue.enqueue_sync(
        provider=provider,
        tenant_id='tenant-a',
        business_id='max-biz',
        operation='message_send',
        mode='live',
        payload=payload,
    )
    queued = store.get(tenant_id='tenant-a', job_id=dispatched.job_id)
    assert queued is not None and queued.max_attempts == 6
    assert queued.claim_expiry_policy is JobClaimExpiryPolicy.DEAD_LETTER_AMBIGUOUS

    report = queue.tick(provider_registry={'max_messaging': provider}, tenant_id='tenant-a', job_id=dispatched.job_id)
    retried = store.get(tenant_id='tenant-a', job_id=dispatched.job_id)
    assert report['retried'] == 1 and report['dead_lettered'] == 0
    assert retried is not None and retried.state is JobState.PENDING and retried.attempts == 1
    assert retried.claim_expiry_policy is JobClaimExpiryPolicy.RETRY_IF_BUDGET
    assert 36 <= (retried.run_at - retried.updated_at).total_seconds() <= 38


def test_max_definitive_rejection_flips_claim_policy_before_worker_reschedule(tmp_path: Path) -> None:
    provider, guard, payload = _approved_native_guard(
        provider_key='max_messaging',
        business_id='max-biz',
        message_payload={'chat_id': '99', 'text': 'hello'},
    )
    runtime = _ProviderResultRuntime(
        ProviderSyncRunResult(
            provider_key='max_messaging',
            operation='message_send',
            mode='live',
            status='live_execution_failed',
            accepted=False,
            metadata={
                'parsed_response': {
                    'http_status': 429,
                    'delivery_state': 'rejected',
                    'error_category': 'rate_limit',
                    'retryable': True,
                },
                'retry_policy': {
                    'category': 'rate_limit',
                    'retryable': True,
                    'next_delay_seconds': 37,
                    'max_attempts': 6,
                },
            },
        )
    )
    store = SqliteJobStore(tmp_path / 'max-crash-window.sqlite3')
    queue = ProviderQueueExecutionRuntime(
        InMemorySecretVault(), live_runtime=runtime, store=store, write_guard=guard,
        idempotency_store=InMemoryIdempotencyStore(),
    )
    dispatched = queue.enqueue_sync(
        provider=provider, tenant_id='tenant-a', business_id='max-biz',
        operation='message_send', mode='live', payload=payload,
    )
    claimed = store.claim(
        tenant_id='tenant-a', job_id=dispatched.job_id, owner_id='worker-a', lease_seconds=30,
    )
    assert claimed is not None and claimed.claim_expiry_policy is JobClaimExpiryPolicy.DEAD_LETTER_AMBIGUOUS

    result = queue._runner({'max_messaging': provider})(claimed)

    assert result.ok is False and result.retry_delay_seconds == 37
    after_provider_result = store.get(tenant_id='tenant-a', job_id=dispatched.job_id)
    assert after_provider_result is not None
    assert after_provider_result.state is JobState.CLAIMED
    assert after_provider_result.claim_expiry_policy is JobClaimExpiryPolicy.RETRY_IF_BUDGET


def test_max_guarded_5xx_is_ambiguous_and_never_automatically_replayed(tmp_path: Path) -> None:
    provider, guard, payload = _approved_native_guard(
        provider_key='max_messaging',
        business_id='max-biz',
        message_payload={'chat_id': '99', 'text': 'hello'},
    )
    runtime = _ProviderResultRuntime(
        ProviderSyncRunResult(
            provider_key='max_messaging',
            operation='message_send',
            mode='live',
            status='live_execution_failed',
            accepted=False,
            metadata={
                'parsed_response': {
                    'http_status': 503,
                    'delivery_state': 'rejected',
                    'error_category': 'provider_unavailable',
                    'retryable': True,
                },
                'retry_policy': {
                    'category': 'provider_unavailable',
                    'retryable': True,
                    'next_delay_seconds': 30,
                    'max_attempts': 6,
                },
            },
        )
    )
    store = SqliteJobStore(tmp_path / 'max-ambiguous.sqlite3')
    queue = ProviderQueueExecutionRuntime(
        InMemorySecretVault(),
        live_runtime=runtime,
        store=store,
        write_guard=guard,
        idempotency_store=InMemoryIdempotencyStore(),
    )
    dispatched = queue.enqueue_sync(
        provider=provider,
        tenant_id='tenant-a',
        business_id='max-biz',
        operation='message_send',
        mode='live',
        payload=payload,
    )
    report = queue.tick(provider_registry={'max_messaging': provider}, tenant_id='tenant-a', job_id=dispatched.job_id)
    terminal = store.get(tenant_id='tenant-a', job_id=dispatched.job_id)
    assert report['dead_lettered'] == 1 and report['retried'] == 0
    assert terminal is not None and terminal.state is JobState.DEAD_LETTER
    assert 'ambiguous_delivery' in str(terminal.last_error)


def test_guarded_max_claim_crash_dead_letters_even_with_safe_retry_budget(tmp_path: Path) -> None:
    provider, guard, payload = _approved_native_guard(
        provider_key='max_messaging',
        business_id='max-biz',
        message_payload={'chat_id': '99', 'text': 'hello'},
    )
    runtime = _ProviderResultRuntime(
        ProviderSyncRunResult(
            provider_key='max_messaging',
            operation='message_send',
            mode='live',
            status='live_executed',
            accepted=True,
            metadata={},
        )
    )
    store = SqliteJobStore(tmp_path / 'max-expired-claim.sqlite3')
    queue = ProviderQueueExecutionRuntime(
        InMemorySecretVault(),
        live_runtime=runtime,
        store=store,
        write_guard=guard,
        idempotency_store=InMemoryIdempotencyStore(),
    )
    dispatched = queue.enqueue_sync(
        provider=provider,
        tenant_id='tenant-a',
        business_id='max-biz',
        operation='message_send',
        mode='live',
        payload=payload,
    )
    now = utc_now()
    claimed = store.claim(
        tenant_id='tenant-a',
        job_id=dispatched.job_id,
        owner_id='crashed-provider-worker',
        lease_seconds=1,
        now=now,
    )
    assert claimed is not None and claimed.attempts == 1 and claimed.max_attempts == 6
    store.reap_expired_claims(tenant_id='tenant-a', queue_name='provider_sync', now=now + timedelta(seconds=2))
    terminal = store.get(tenant_id='tenant-a', job_id=dispatched.job_id)
    assert terminal is not None and terminal.state is JobState.DEAD_LETTER
    assert terminal.last_error == 'expired_claim_ambiguous_delivery'


def test_vk_queue_identity_derives_stable_nonzero_provider_random_id() -> None:
    provider, guard, payload = _approved_native_guard(
        provider_key='vk_messaging',
        business_id='vk-biz',
        message_payload={'peer_id': '42', 'text': 'hello', 'random_id': 0},
    )
    vault = InMemorySecretVault()
    for name, value in (('webhook_secret', 'bridge-secret'), ('access_token', 'group-token')):
        vault.seed_plaintext(
            ref=SecretRef(
                tenant_id='tenant-a',
                connector_id=provider.connector_id,
                scope='vk-biz',
                secret_name=f'{provider.connector_id}.{name}',
            ),
            plaintext=value,
        )

    class _Transport:
        def __init__(self) -> None:
            self.random_ids: list[int] = []

        def execute(self, **kwargs):
            self.random_ids.append(int(kwargs['payload']['random_id']))
            return {
                'http_status': 200,
                'response_body': '{"response":777}',
                'parsed_response': {
                    'http_status': 200,
                    'ok': True,
                    'resource_id': '777',
                    'error_code': None,
                    'retryable': False,
                    'delivery_state': 'accepted',
                },
                '_response_ok': True,
            }

    transport = _Transport()
    runtime = ProviderLiveSyncRuntime(vault, transports={'vk_messaging': transport}, write_guard=guard)
    for job_id in ('provider-sync-vk-stable', 'provider-sync-vk-stable', 'provider-sync-vk-other'):
        result = runtime.run(
            provider=provider,
            tenant_id='tenant-a',
            business_id='vk-biz',
            operation='message_send',
            mode='live',
            payload=payload,
            _queue_job_id=job_id,
        )
        assert result.accepted is True
    first, replay, other = transport.random_ids
    assert first == replay
    assert first != other
    assert 0 < first <= 2_147_483_647
    assert 0 < other <= 2_147_483_647


def test_native_media_approval_binds_exact_file_bytes_and_rejects_path_content_swap(tmp_path: Path) -> None:
    source = tmp_path / 'approved-voice.ogg'
    source.write_bytes(b'approved-bytes')
    approval_store = InMemoryApprovalStore()
    workflow = ApprovalWorkflow(store=approval_store)
    gate = ApprovalExecutionGate(
        approval_policy_engine=ApprovalPolicyEngine(change_control_policy=ChangeControlPolicy()),
        approval_workflow=workflow,
    )
    guard = ProviderRuntimeWriteGuard(approval_gate=gate, approval_store=approval_store)
    provider = provider_map()['max_messaging']
    store = SqliteJobStore(tmp_path / 'media-approval.sqlite3')
    queue = ProviderQueueExecutionRuntime(
        InMemorySecretVault(), live_runtime=_ProviderResultRuntime(
            ProviderSyncRunResult(provider_key='max_messaging', operation='message_send', mode='live', status='unused', accepted=False)
        ), store=store, write_guard=guard, idempotency_store=InMemoryIdempotencyStore(),
    )
    approval = {'decision_id': 'dec-media', 'execution_id': 'exec-media'}
    payload = {
        'chat_id': '99', 'text': 'listen',
        'attachments': [{'kind': 'voice', 'source': str(source)}],
        '_approval': approval,
    }
    first = queue.enqueue_sync(
        provider=provider, tenant_id='tenant-a', business_id='max-biz',
        operation='message_send', mode='live', payload=payload,
    )
    evidence = dict(first.metadata['provider_write_guard']['metadata']['approval'])
    approval_id = str(evidence['approval_id'])
    record = workflow.get(approval_id)
    assert record is not None
    approved_attachment = record.request.metadata['approval_resume_context']['payload']['attachments'][0]
    assert approved_attachment['source'] == str(source)
    assert len(approved_attachment['source_digest']) == 64
    workflow.evaluate(
        ApprovalDecision(
            approval_id=approval_id, tenant_id='tenant-a', actor_id='owner-approver',
            role_id=RoleId.OWNER, outcome=ApprovalOutcome.APPROVE, rationale='approve exact media bytes',
        )
    )
    source.write_bytes(b'changed-after-approval')
    resumed = {
        **payload,
        '_approval': {**approval, 'approval_id': approval_id},
    }
    second = queue.enqueue_sync(
        provider=provider, tenant_id='tenant-a', business_id='max-biz',
        operation='message_send', mode='live', payload=resumed,
    )
    assert second.queued is False
    guard_view = dict(second.metadata['provider_write_guard'])
    assert guard_view['reason'] == 'approval_subject_mismatch'
    assert store.count(tenant_id='tenant-a', queue_name='provider_sync') == 0


def test_native_media_missing_source_fails_before_approval_or_queue(tmp_path: Path) -> None:
    provider = provider_map()['vk_messaging']
    queue = ProviderQueueExecutionRuntime(
        InMemorySecretVault(),
        live_runtime=_ProviderResultRuntime(
            ProviderSyncRunResult(provider_key='vk_messaging', operation='message_send', mode='live', status='unused', accepted=False)
        ),
        store=SqliteJobStore(tmp_path / 'missing-media.sqlite3'),
        idempotency_store=InMemoryIdempotencyStore(),
    )
    missing = tmp_path / 'does-not-exist.ogg'
    result = queue.enqueue_sync(
        provider=provider, tenant_id='tenant-a', business_id='vk-biz', operation='message_send', mode='live',
        payload={'peer_id': '42', 'text': 'listen', 'attachments': [{'kind': 'voice', 'source': str(missing)}], '_approval': {'decision_id': 'd', 'execution_id': 'e'}},
    )
    assert result.queued is False and result.status == 'canonical_media_source_invalid'
    assert str(missing) not in repr(result.metadata)
    assert result.metadata['fail_closed_before_queue'] is True
