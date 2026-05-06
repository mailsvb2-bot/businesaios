from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _text(path: str) -> str:
    return (PROJECT_ROOT / path).read_text(encoding='utf-8')


def test_headless_decision_gateway_declares_single_path_owner() -> None:
    text = _text('application/headless/decision_gateway.py')
    assert 'CANON_HEADLESS_DECISION_GATEWAY_SINGLE_PATH = True' in text
    assert 'CANON_HEADLESS_DECISION_GATEWAY_ISSUE_OWNER = True' in text
    assert 'def issue_headless_decision(' in text


def test_autonomy_decision_step_uses_headless_gateway_owner() -> None:
    text = _text('application/autonomy/autonomy_decision_step.py')
    assert 'issue_headless_decision(' in text
    assert '._decision_core.optimize(' not in text
    assert '._decision_core.issue(' not in text
    assert '._decision_core.decide(' not in text


def test_headless_contract_validates_via_gateway_owner() -> None:
    text = _text('execution/headless_contract.py')
    assert 'validate_headless_decision_core' in text
    assert 'decision_core must provide callable issue()' in text
