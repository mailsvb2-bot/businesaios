from __future__ import annotations

from types import SimpleNamespace

import pytest

from entrypoints.api.owner_action_draft import OwnerActionDraftError, OwnerActionDraftProjector


class _Ledger:
    def __init__(self, record: dict | None) -> None:
        self.record = record
        self.read_ids: list[str] = []

    def read(self, run_id: str) -> dict:
        self.read_ids.append(run_id)
        if self.record is None:
            raise FileNotFoundError(run_id)
        return self.record


class _Provider:
    def __init__(self, ledger: _Ledger) -> None:
        self.runtime = SimpleNamespace(ledger=ledger)

    def get_runtime(self):
        return self.runtime


def _record(*, action_type: str = "send_message@v1", payload: dict | None = None, executed: bool = False, verified: bool = False) -> dict:
    return {
        "tenant_id": "tenant-a",
        "business_id": "business-a",
        "goal": "Вернуть клиента",
        "canonical_run_artifact": {
            "step_artifacts": [{
                "decision_id": "decision-1",
                "action_id": "action-1",
                "action_type": action_type,
                "status": "blocked_by_policy",
                "operator_required": True,
                "executed": executed,
                "verified": verified,
                "payload": dict(payload or {"channel": "vk", "user_id": "12345", "text": "Здравствуйте"}),
            }]
        },
    }


def _projector(record: dict | None):
    ledger = _Ledger(record)
    return OwnerActionDraftProjector(runtime_provider=_Provider(ledger)), ledger


def test_persisted_decisioncore_message_projects_to_editable_non_executing_draft() -> None:
    projector, ledger = _projector(_record())
    result = projector.project(tenant_id="tenant-a", business_id="business-a", run_id="01234567-89ab-cdef-0123-456789abcdef", decision_id="decision-1", action_id="action-1")
    assert ledger.read_ids == ["01234567-89ab-cdef-0123-456789abcdef"]
    assert result["source"] == "decision_core_ledger"
    assert result["suggested_provider_key"] == "vk_messaging"
    assert result["recipient"] == "12345"
    assert result["text"] == "Здравствуйте"
    assert result["editable"] is True
    assert result["execution_allowed"] is False
    assert result["next_boundary"] == "/actions/execute"


def test_placeholder_or_unbound_recipient_is_never_promoted_to_customer_target() -> None:
    projector, _ = _projector(_record(payload={"user_id": "anonymous", "text": "draft"}))
    result = projector.project(tenant_id="tenant-a", business_id="business-a", run_id="run-safe", decision_id="decision-1", action_id="action-1")
    assert result["recipient"] == ""
    assert result["suggested_provider_key"] == ""
    assert result["requires_recipient"] is True
    assert result["requires_channel"] is True


@pytest.mark.parametrize("tenant_id,business_id", [("tenant-b", "business-a"), ("tenant-a", "business-b")])
def test_cross_scope_decision_run_is_hidden(tenant_id: str, business_id: str) -> None:
    projector, _ = _projector(_record())
    with pytest.raises(OwnerActionDraftError) as exc:
        projector.project(tenant_id=tenant_id, business_id=business_id, run_id="run-safe", decision_id="decision-1", action_id="action-1")
    assert (exc.value.code, exc.value.status_code) == ("decision_run_not_found", 404)


def test_decision_and_action_identity_must_match_persisted_step() -> None:
    projector, _ = _projector(_record())
    with pytest.raises(OwnerActionDraftError) as exc:
        projector.project(tenant_id="tenant-a", business_id="business-a", run_id="run-safe", decision_id="decision-other", action_id="action-1")
    assert (exc.value.code, exc.value.status_code) == ("decision_step_not_found", 404)


@pytest.mark.parametrize("record,code", [(_record(action_type="notify_owner"), "decision_action_not_handoff_eligible"), (_record(executed=True), "decision_action_already_executed"), (_record(verified=True), "decision_action_already_executed")])
def test_only_unexecuted_send_message_steps_can_be_handed_off(record: dict, code: str) -> None:
    projector, _ = _projector(record)
    with pytest.raises(OwnerActionDraftError) as exc:
        projector.project(tenant_id="tenant-a", business_id="business-a", run_id="run-safe", decision_id="decision-1", action_id="action-1")
    assert exc.value.code == code
    assert exc.value.status_code == 409


def test_run_id_is_validated_before_ledger_path_access() -> None:
    projector, ledger = _projector(_record())
    with pytest.raises(OwnerActionDraftError) as exc:
        projector.project(tenant_id="tenant-a", business_id="business-a", run_id="../other-business", decision_id="decision-1", action_id="action-1")
    assert (exc.value.code, exc.value.status_code) == ("decision_run_id_invalid", 422)
    assert ledger.read_ids == []
