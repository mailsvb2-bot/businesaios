from __future__ import annotations

from contracts.action_result import ActionResult
from execution.action_result_store import ActionResultStore
from execution.action_retry import ActionRetry
from execution.run_result_store import ActionResultStore as CanonActionResultStore
from execution.run_retry_policy import ActionRetry as CanonActionRetry


def test_action_result_store_reexports_canonical_store_without_changing_behavior() -> None:
    assert ActionResultStore is CanonActionResultStore
    store = ActionResultStore()
    result = ActionResult(action_id='a1', status='accepted', message='ok')
    store.save('a1', result)
    assert store.get('a1') is result


def test_action_retry_reexports_canonical_retry_without_changing_behavior() -> None:
    assert ActionRetry is CanonActionRetry
    retry = ActionRetry()
    assert retry.should_retry(ActionResult(action_id='a1', status='temporary_failure', message='retry')) is True
    assert retry.should_retry(ActionResult(action_id='a2', status='accepted', message='ok')) is False
