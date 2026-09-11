from __future__ import annotations

from types import SimpleNamespace

from application.business_autonomy.provider_catalog import provider_map
from application.business_autonomy.provider_runtime_contract import ProviderSyncRunResult
from contracts.owner_decision_provenance import normalize_owner_decision_provenance
from entrypoints.api.provider_admin_route_handlers import ProviderAdminRouteHandlers
from execution.approval_execution_gate import ApprovalExecutionGate
from execution.approval_policy_engine import ApprovalPolicyEngine
from governance.approval_store import InMemoryApprovalStore
from governance.approval_workflow import ApprovalWorkflow
from governance.change_control_policy import ChangeControlPolicy
from runtime.business_autonomy.provider_live_sync_runtime import ProviderLiveSyncRuntime
from runtime.business_autonomy.provider_queue_execution import ProviderQueueExecutionRuntime
from runtime.business_autonomy.provider_runtime_write_guard import ProviderRuntimeWriteGuard
from runtime.business_autonomy.provider_sync_history import InMemoryProviderSyncHistoryStore, ProviderSyncHistory
from runtime.messaging.bootstrap import _NativeProviderQueueAdapter
from runtime.messaging.outbound_message import OutboundMessage
from runtime.queue.job_store_sqlite import SqliteJobStore
from security.secret_vault import InMemorySecretVault


def _provenance() -> dict[str, str]:
    return {
        "source": "owner_decision_draft",
        "verification": "server_ledger",
        "tenant_id": "tenant-a",
        "business_id": "business-a",
        "run_id": "run-1",
        "decision_id": "decision-source-1",
        "action_id": "action-source-1",
        "action_type": "send_message@v1",
    }


def test_native_adapter_carries_only_server_verified_provenance_as_internal_metadata() -> None:
    class _Registry:
        def get(self, key):
            return provider_map()[key]

    class _Service:
        provider_registry = _Registry()
        def __init__(self):
            self.calls = []
        def execute_queued_provider_sync(self, **kwargs):
            self.calls.append(kwargs)
            return {"dispatch": {"queued": False, "status": "blocked", "metadata": {}}, "result": None}

    service = _Service()
    msg = OutboundMessage(
        decision_id="api-command:tenant-a:draft-1",
        correlation_id="corr-1",
        tenant_id="tenant-a",
        business_id="business-a",
        user_id="42",
        channel="vk",
        text="hello",
        track_payload={**_provenance(), "_provider_native": {"business_id": "business-a", "peer_id": "42"}},
    )
    _NativeProviderQueueAdapter("vk", service_factory=lambda: service).send(msg)
    sent = service.calls[0]["payload"]
    assert sent["_decision_provenance"] == _provenance()
    assert sent["_approval"]["decision_id"] == "api-command:tenant-a:draft-1"


def test_write_guard_persists_provenance_with_approval_but_excludes_it_from_provider_subject() -> None:
    store = InMemoryApprovalStore()
    workflow = ApprovalWorkflow(store=store)
    gate = ApprovalExecutionGate(
        approval_policy_engine=ApprovalPolicyEngine(change_control_policy=ChangeControlPolicy()),
        approval_workflow=workflow,
    )
    guard = ProviderRuntimeWriteGuard(approval_gate=gate, approval_store=store)
    provider = provider_map()["vk_messaging"]
    payload = {
        "peer_id": "42",
        "message": "hello",
        "_decision_provenance": _provenance(),
        "_approval": {"decision_id": "api-command:tenant-a:draft-1", "execution_id": "api-command:tenant-a:draft-1"},
    }
    denied = guard.evaluate(provider=provider, operation="message_send", mode="live", tenant_id="tenant-a", business_id="business-a", payload=payload)
    record = workflow.get(str(denied.metadata["approval"]["approval_id"]))
    assert record is not None
    assert record.request.metadata["decision_provenance"] == _provenance()
    assert "_decision_provenance" not in record.request.metadata["approval_resume_context"]["payload"]

    tampered = {**payload, "_decision_provenance": {**_provenance(), "verification": "browser"}}
    rejected = guard.evaluate(provider=provider, operation="message_send", mode="live", tenant_id="tenant-a", business_id="business-a", payload=tampered)
    assert rejected.allowed is False and rejected.reason == "decision_provenance_invalid"


def test_approval_resume_rebinds_persisted_provenance_and_rejects_scope_mismatch() -> None:
    provenance = _provenance()

    class _Store:
        def __init__(self, value): self.value = value
        def get(self, _approval_id): return self.value

    class _Registry:
        def get(self, key): return provider_map()[key]

    class _Service:
        provider_registry = _Registry()
        def __init__(self): self.calls = []
        def execute_queued_provider_sync(self, **kwargs):
            self.calls.append(kwargs)
            return {"dispatch": {"queued": True, "job_id": "job-1"}, "worker": {"succeeded": 1}, "result": {"accepted": True, "status": "live_executed", "parsed_response": {"resource_id": "77"}}}

    def record(prov):
        return SimpleNamespace(
            status=SimpleNamespace(value="approved"),
            request=SimpleNamespace(
                approval_id="ap-1", tenant_id="tenant-a", subject_id="api-command:tenant-a:draft-1",
                metadata={
                    "action_name": "provider.vk_messaging.message_send",
                    "decision_id": "api-command:tenant-a:draft-1",
                    "decision_provenance": prov,
                    "approval_resume_context": {"provider_key": "vk_messaging", "business_id": "business-a", "operation": "message_send", "payload": {"peer_id": "42", "random_id": 0, "message": "hello", "group_id": "1"}},
                },
            ),
        )

    envelope = SimpleNamespace(decision=SimpleNamespace(decision_id="api-command:tenant-a:draft-1", action="send_message@v1", payload={"tenant_id": "tenant-a", "business_id": "business-a"}))
    service = _Service()
    handlers = ProviderAdminRouteHandlers(service_factory=lambda **_: service, approval_store_factory=lambda: _Store(record(provenance)), decision_loader=lambda **_: envelope)
    result = handlers.resume_approved_message(tenant_id="tenant-a", approval_id="ap-1")
    assert result["decision_provenance"] == provenance
    assert service.calls[0]["payload"]["_decision_provenance"] == provenance

    bad = {**provenance, "business_id": "business-b"}
    bad_handlers = ProviderAdminRouteHandlers(service_factory=lambda **_: service, approval_store_factory=lambda: _Store(record(bad)), decision_loader=lambda **_: envelope)
    try:
        bad_handlers.resume_approved_message(tenant_id="tenant-a", approval_id="ap-1")
    except RuntimeError as exc:
        assert "provider_approval_decision_provenance_business_mismatch" in str(exc)
    else:
        raise AssertionError("scope-mismatched provenance must fail closed")


def test_provider_history_records_provenance_without_sending_it_to_audit_payload() -> None:
    provenance = _provenance()
    history = ProviderSyncHistory(store=InMemoryProviderSyncHistoryStore())

    class _Audit:
        def __init__(self): self.payloads = []
        def record_sync_run(self, **kwargs):
            self.payloads.append(dict(kwargs["payload"]))
            return {"recorded_at_utc": "2026-09-11T10:00:00Z"}

    class _Export:
        def export_runtime_event(self, **_kwargs): return {}

    class _Observability:
        def record_sync(self, **_kwargs): return None

    audit = _Audit()
    runtime = ProviderLiveSyncRuntime(
        secret_vault=InMemorySecretVault(),
        transports={},
        audit_recorder=audit,
        export_bridge=_Export(),
        observability=_Observability(),
        sync_history=history,
    )
    result = runtime._finalize_result(
        tenant_id="tenant-a",
        business_id="business-a",
        provider=provider_map()["vk_messaging"],
        operation="message_send",
        mode="live",
        result=ProviderSyncRunResult(provider_key="vk_messaging", operation="message_send", mode="live", status="live_executed", accepted=True, metadata={"parsed_response": {"resource_id": "77"}}),
        payload={"peer_id": "42", "_provider_queue_job_id": "job-1", "_decision_provenance": provenance},
    )
    assert result.metadata["history_row"]["decision_provenance"] == provenance
    assert "_decision_provenance" not in audit.payloads[0]


def test_queue_rejects_unverified_provenance_before_job_persistence(tmp_path) -> None:
    queue = ProviderQueueExecutionRuntime(
        secret_vault=InMemorySecretVault(),
        live_runtime=ProviderLiveSyncRuntime(secret_vault=InMemorySecretVault(), transports={}),
        store=SqliteJobStore(tmp_path / "jobs.sqlite3"),
    )
    result = queue.enqueue_sync(
        provider=provider_map()["vk_messaging"],
        tenant_id="tenant-a",
        business_id="business-a",
        operation="message_send",
        mode="live",
        payload={"peer_id": "42", "message": "hello", "_decision_provenance": {**_provenance(), "verification": "browser"}},
    )
    assert result.queued is False
    assert result.status == "decision_provenance_invalid"
    assert result.metadata["fail_closed_before_queue"] is True


def test_provenance_contract_rejects_incomplete_or_unverified_values() -> None:
    assert normalize_owner_decision_provenance(_provenance()) == _provenance()
    assert normalize_owner_decision_provenance({**_provenance(), "run_id": ""}) == {}
    assert normalize_owner_decision_provenance({**_provenance(), "verification": "browser"}) == {}
