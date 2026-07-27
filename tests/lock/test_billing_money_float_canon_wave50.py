from __future__ import annotations

from pathlib import Path

from tools.billing_money_float_scanner import scan_billing_money_float_arithmetic


def test_billing_money_arithmetic_has_no_direct_float_path() -> None:
    root = Path(__file__).resolve().parents[2]
    violations = scan_billing_money_float_arithmetic(root)
    assert not violations, "\n".join(
        f"{item.path}:{item.line}: {item.rule}: {item.expression}"
        for item in violations
    )
