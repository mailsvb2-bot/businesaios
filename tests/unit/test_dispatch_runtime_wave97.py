from contracts.executable_action import ExecutableAction
from execution.action_dispatcher import ActionDispatcher
from execution.action_idempotency import ActionIdempotency
from execution.action_result_store import ActionResultStore
from execution.action_runner import ActionRunner
from execution.action_validator import ActionValidator
from observability.action_audit_log import ActionAuditLog
from shared.registry import ActionRunnerRegistry


class _Runner:
    def run(self, action):
        from contracts.action_result import ActionResult

        return ActionResult(action_id=action.action_id, status='accepted', message='ok', payload={'ran': True})


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


def test_action_dispatcher_uses_dispatch_runtime_without_changing_observable_side_effects() -> None:
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
    assert dispatcher._metrics.get('action_dispatch.accepted') == 1
