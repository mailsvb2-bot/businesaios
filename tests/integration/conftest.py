from __future__ import annotations

from typing import Any

import pytest

from core.ai import (
    _reset_decision_core_singleton_for_tests,
    set_decision_core_singleton,
)


class _OptimizeIssueAdapter:
    """Test-only ABI adapter; selection remains owned by the wrapped fake."""

    def __init__(self, delegate: object) -> None:
        self._delegate = delegate

    def issue(self, state: Any) -> Any:
        optimize = getattr(self._delegate, "optimize", None)
        if not callable(optimize):
            raise TypeError("integration fake must provide issue() or optimize()")
        return optimize(state)


def _canonical_test_issuer(candidate: object) -> object:
    if callable(getattr(candidate, "issue", None)):
        return candidate
    if callable(getattr(candidate, "optimize", None)):
        return _OptimizeIssueAdapter(candidate)
    return candidate


@pytest.fixture(autouse=True)
def _register_headless_integration_issuer(monkeypatch):
    """Route deterministic integration fakes through the real singleton law.

    Integration scenarios construct independent headless runtimes, sometimes
    more than once inside one test. Each construction is therefore treated as a
    fresh test runtime through the private reset boundary; production code and
    production singleton behavior are not modified.
    """

    from application.headless.contract import HeadlessExecutionContract

    original_init = HeadlessExecutionContract.__init__

    def canonical_init(self, *args, **kwargs):
        candidate = kwargs.get("decision_core")
        issuer = _canonical_test_issuer(candidate)
        if callable(getattr(issuer, "issue", None)):
            _reset_decision_core_singleton_for_tests()
            set_decision_core_singleton(issuer)
            kwargs["decision_core"] = issuer
        return original_init(self, *args, **kwargs)

    monkeypatch.setattr(
        HeadlessExecutionContract,
        "__init__",
        canonical_init,
    )
    yield


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        item.add_marker(pytest.mark.integration)
