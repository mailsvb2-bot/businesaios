from pathlib import Path


def test_dispatch_runtime_is_execution_owned() -> None:
    content = Path('execution/dispatch_runtime.py').read_text(encoding='utf-8')
    assert 'class DispatchRuntime:' in content
    assert 'result = self.chain.dispatch(action)' in content
    assert "self.metrics.inc(f'action_dispatch.{result.status}')" in content


def test_action_dispatcher_delegates_runtime_side_effects_to_dispatch_runtime() -> None:
    content = Path('execution/action_dispatcher.py').read_text(encoding='utf-8')
    assert 'from execution.dispatch_runtime import DispatchRuntime' in content
    assert 'self._runtime = DispatchRuntime(' in content
    assert 'return self._runtime.dispatch(action)' in content
