from contracts.executable_action import ExecutableAction
from execution.runners.internal.create_experiment import Runner as CreateExperimentRunner
from execution.runners.internal.notify_owner import Runner as NotifyOwnerRunner
from execution.runners.internal.rollback_action import Runner as RollbackRunner


def _action() -> ExecutableAction:
    return ExecutableAction(action_id='a1', action_type='notify_owner', channel='internal', payload={'x': 1})


def test_internal_runners_share_accepted_contract() -> None:
    for runner in (NotifyOwnerRunner(), RollbackRunner(), CreateExperimentRunner()):
        result = runner.run(_action())
        assert result.status == 'accepted'
        assert result.payload['attempted'] is True
        assert result.payload['executed'] is True
        assert result.payload['verified'] is False
