from contracts.action_result import ActionResult
from contracts.executable_action import ExecutableAction
from execution.action_dispatcher import ActionDispatcher
from execution.action_idempotency import ActionIdempotency
from execution.action_result_store import ActionResultStore
from execution.action_runner import ActionRunner
from execution.action_validator import ActionValidator
from execution.dispatch_runner_chain import DispatchRunnerChain
from observability.action_audit_log import ActionAuditLog
from shared.registry import ActionRunnerRegistry


class _Runner:
    def __init__(self, status='accepted'):
        self.calls = []
        self.status = status

    def run(self, action):
        self.calls.append(action)
        return ActionResult(action_id=action.action_id, status=self.status, message='ok', payload={'ran': True})


def _action(**overrides):
    data = dict(
        action_id='a1',
        action_type='notify_owner',
        channel='email',
        payload={},
        decision_id='d1',
        correlation_id='c1',
    )
    data.update(overrides)
    return ExecutableAction(**data)


def test_dispatch_runner_chain_preserves_validation_and_duplicate_semantics() -> None:
    runner = _Runner()
    chain = DispatchRunnerChain(ActionValidator(), runner, ActionIdempotency())

    rejected = chain.dispatch(_action(action_id='', decision_id=''))
    duplicate_first = chain.dispatch(_action(action_id='dup'))
    duplicate_second = chain.dispatch(_action(action_id='dup'))

    assert rejected.status == 'rejected'
    assert rejected.payload['errors']
    assert duplicate_first.status == 'accepted'
    assert duplicate_second.status == 'duplicate'
    assert len(runner.calls) == 1


def test_action_dispatcher_uses_chain_without_changing_persisted_result() -> None:
    registry = ActionRunnerRegistry()
    registry.register('notify_owner', _Runner())
    dispatcher = ActionDispatcher(
        ActionValidator(),
        ActionRunner(registry),
        ActionResultStore(),
        ActionAuditLog(),
        ActionIdempotency(),
    )

    result = dispatcher.dispatch(_action())

    assert result.status == 'accepted'
    assert dispatcher._store.get('a1').status == 'accepted'
    assert dispatcher._audit_log.records[-1]['status'] == 'accepted'
