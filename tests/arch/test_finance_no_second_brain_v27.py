
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_finance_strategic_contour_stays_inside_finance_domain() -> None:
    assert (ROOT / 'core' / 'finance' / 'strategic').exists()
    assert not (ROOT / 'core' / 'strategic_finance').exists()


def test_finance_contour_has_no_decision_core_clone() -> None:
    for path in (ROOT / 'core' / 'finance' / 'strategic').rglob('*.py'):
        text = path.read_text(encoding='utf-8')
        assert 'class DecisionCore' not in text


def test_finance_boot_is_wiring_only() -> None:
    text = (ROOT / 'runtime' / 'boot' / 'finance_boot.py').read_text(encoding='utf-8')
    assert 'CANON_BOOT_WIRING_ONLY = True' in text
    assert 'StrategicFinanceService' in text
