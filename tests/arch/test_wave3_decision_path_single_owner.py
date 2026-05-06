from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_decision_path_lock_declares_single_owner_contract() -> None:
    text = _text('runtime/decision_path_lock.py')
    assert 'CANON_DECISION_PATH_LOCK_SINGLE_OWNER = True' in text
    assert 'CANON_DECISION_PATH_LOCK_FAIL_CLOSED = True' in text
    assert "'world_state'," in text
    assert "'decision_core'," in text
    assert "'executor'," in text
    assert 'def issue_locked_decision(' in text


def test_runtime_gateway_uses_decision_path_lock_owner() -> None:
    text = _text('runtime/decision_gateway.py')
    assert 'from runtime.decision_path_lock import issue_locked_decision' in text
    assert 'issue_locked_decision(decision_core=self.issuer, state=enriched_state)' in text
    assert '.issue(enriched_state)' not in text


def test_headless_gateway_uses_decision_path_lock_owner() -> None:
    text = _text('application/headless/decision_gateway.py')
    assert 'from runtime.decision_path_lock import DecisionPathLockError, issue_locked_decision, resolve_decision_issue_callable' in text
    assert 'issue_locked_decision(decision_core=self.decision_core, state=state)' in text
    assert "for attribute_name in ('optimize', 'issue', 'decide')" not in text


def test_headless_contract_requires_issue_only() -> None:
    text = _text('execution/headless_contract.py')
    assert 'decision_core must provide callable issue()' in text
    assert 'issue(), optimize(), or decide()' not in text
