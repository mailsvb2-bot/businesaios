from __future__ import annotations

from runtime.execution.contracts import RUNTIME_EXECUTOR_CONTRACT_VERSION, RuntimeExecutorPort


def test_executor_contract_resolves_to_canonical_owner() -> None:
    assert RuntimeExecutorPort is not None
    assert RUNTIME_EXECUTOR_CONTRACT_VERSION
