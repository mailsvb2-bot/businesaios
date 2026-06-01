from __future__ import annotations

from interfaces.cli import headless_product


def test_cli_capability_matrix_outputs_operational_truth() -> None:
    code = headless_product.main(["capability-matrix"])
    assert code == 0
