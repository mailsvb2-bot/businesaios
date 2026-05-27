import pytest

from execution.action_dispatcher import ActionDispatcher
from execution.action_idempotency import ActionIdempotency
from execution.action_result_store import ActionResultStore
from execution.action_runner import ActionRunner
from execution.action_validator import ActionValidator
from observability.action_audit_log import ActionAuditLog
from shared.registry import ActionRunnerRegistry


class _Runner:
    def run(self, action):
        return {'status': 'accepted'}


def test_dispatcher_rejects_non_contract_payloads():
    registry = ActionRunnerRegistry()
    registry.register('notify_owner', _Runner())
    dispatcher = ActionDispatcher(ActionValidator(), ActionRunner(registry), ActionResultStore(), ActionAuditLog(), ActionIdempotency())
    with pytest.raises(TypeError):
        dispatcher.dispatch({'action_type': 'notify_owner'})
