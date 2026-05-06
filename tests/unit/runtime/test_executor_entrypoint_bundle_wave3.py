from runtime.execution.executor_entrypoint_bundle import build_executor_entrypoint_bundle


class _Decision:
    payload = {'user_id': 'u1'}
    decision_id = 'd1'
    correlation_id = 'c1'
    snapshot_id = 's1'


class _Env:
    decision = _Decision()


class _Executor:
    def __init__(self):
        self.called = False
    def _execute(self, env, *, depth, timescale):
        self.called = True
        return {'ok': True, 'depth': depth}


class _Span:
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc, tb):
        return False


def test_executor_entrypoint_bundle_runs_default_execute(monkeypatch) -> None:
    import runtime.execution.executor_entrypoint as entry
    monkeypatch.setattr(entry, 'execute_total_span', lambda **kwargs: _Span())
    monkeypatch.setattr(entry, 'extract_correlation_key', lambda store, snapshot_id: 'ck')
    monkeypatch.setattr(entry, 'run_with_bound_execution_context', lambda **kwargs: kwargs['run']())

    executor = _Executor()
    bundle = build_executor_entrypoint_bundle(
        event_log=object(),
        snapshot_store=object(),
        executor_context_cm=lambda name: _Span(),
    )
    result = bundle.run(executor=executor, env=_Env())
    assert executor.called is True
    assert result['ok'] is True
