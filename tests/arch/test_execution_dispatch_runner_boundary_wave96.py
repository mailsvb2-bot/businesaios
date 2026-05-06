from pathlib import Path


def test_dispatch_runner_chain_is_execution_owned() -> None:
    content = Path('execution/dispatch_runner_chain.py').read_text(encoding='utf-8')
    assert 'class DispatchRunnerChain:' in content
    assert 'class ActionRunPort(Protocol):' in content
    assert "status='duplicate'" in content


def test_action_dispatcher_delegates_core_chain_logic() -> None:
    content = Path('execution/action_dispatcher.py').read_text(encoding='utf-8')
    assert 'from execution.dispatch_runner_chain import DispatchRunnerChain' in content
    assert 'self._chain = DispatchRunnerChain' in content
    assert 'self._runtime = DispatchRuntime(' in content or 'result = self._chain.dispatch(action)' in content
