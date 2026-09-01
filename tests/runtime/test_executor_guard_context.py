import pytest


def test_runtime_guard_raises_outside_executor_context() -> None:
    from runtime.executor import assert_called_from_executor

    with pytest.raises(RuntimeError):
        assert_called_from_executor("must fail")


def test_runtime_guard_passes_inside_executor_context() -> None:
    from runtime.executor import assert_called_from_executor, executor_context

    with executor_context("test"):
        assert_called_from_executor("should not fail")


def test_execution_entrypoint_binds_signed_business_scope_and_resets_it() -> None:
    from contextlib import contextmanager
    from types import SimpleNamespace

    from runtime.execution.context import current_execution_business_id
    from runtime.execution.entrypoint_context import run_with_bound_execution_context

    @contextmanager
    def _executor_context(_name: str):
        yield

    env = SimpleNamespace(
        decision=SimpleNamespace(
            decision_id="decision-1",
            correlation_id="correlation-1",
            payload={"tenant_id": "tenant-a", "business_id": "business-b"},
        )
    )
    observed = run_with_bound_execution_context(
        env=env,
        executor_context_cm=_executor_context,
        context_name="test",
        execute_callback=current_execution_business_id,
    )

    assert observed == "business-b"
    assert current_execution_business_id() == ""


def test_execution_entrypoint_resets_business_scope_after_failure() -> None:
    from contextlib import contextmanager
    from types import SimpleNamespace

    from runtime.execution.context import current_execution_business_id
    from runtime.execution.entrypoint_context import run_with_bound_execution_context

    @contextmanager
    def _executor_context(_name: str):
        yield

    def _fail() -> None:
        assert current_execution_business_id() == "business-b"
        raise RuntimeError("expected")

    env = SimpleNamespace(
        decision=SimpleNamespace(
            decision_id="decision-2",
            correlation_id="correlation-2",
            payload={"business_id": "business-b"},
        )
    )
    with pytest.raises(RuntimeError, match="expected"):
        run_with_bound_execution_context(
            env=env,
            executor_context_cm=_executor_context,
            context_name="test",
            execute_callback=_fail,
        )
    assert current_execution_business_id() == ""
