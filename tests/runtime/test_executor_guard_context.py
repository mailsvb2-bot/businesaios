import pytest


def test_runtime_guard_raises_outside_executor_context() -> None:
    from runtime.executor import assert_called_from_executor

    with pytest.raises(RuntimeError):
        assert_called_from_executor("must fail")


def test_runtime_guard_passes_inside_executor_context() -> None:
    from runtime.executor import assert_called_from_executor, executor_context

    with executor_context("test"):
        assert_called_from_executor("should not fail")
