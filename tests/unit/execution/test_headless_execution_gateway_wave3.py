from application.headless.execution_gateway import (
    HeadlessExecutionGatewayContractError,
    execute_headless_envelope,
    validate_headless_executor,
)


class _Decision:
    decision_id = 'd-1'
    correlation_id = 'c-1'


class _Envelope:
    decision = _Decision()


class _Executor:
    def __init__(self) -> None:
        self.seen = []

    def execute(self, envelope):
        self.seen.append(envelope)
        return {'ok': True, 'envelope': envelope}


class _BadExecutor:
    pass


def test_execute_headless_envelope_uses_executor_execute() -> None:
    executor = _Executor()
    envelope = _Envelope()
    result = execute_headless_envelope(executor=executor, envelope=envelope)
    assert result == {'ok': True, 'envelope': envelope}
    assert executor.seen == [envelope]


def test_validate_headless_executor_rejects_missing_execute() -> None:
    try:
        validate_headless_executor(_BadExecutor())
    except HeadlessExecutionGatewayContractError as exc:
        assert 'executor_must_provide_callable_execute' in str(exc)
    else:
        raise AssertionError('expected HeadlessExecutionGatewayContractError')



def test_execute_headless_envelope_fails_closed_on_invalid_contract() -> None:
    executor = _Executor()
    try:
        execute_headless_envelope(executor=executor, envelope=object())
    except HeadlessExecutionGatewayContractError as exc:
        assert 'execution_envelope_missing_decision' in str(exc)
    else:
        raise AssertionError('expected HeadlessExecutionGatewayContractError')
