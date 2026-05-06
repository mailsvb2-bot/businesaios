from __future__ import annotations

import pytest

from tests._infra.repo_scan import format_hits, scan_lines


@pytest.mark.lock
def test_lock_product_contract_defined_only_once() -> None:
    """ProductContract must be defined only in contracts/product_contract.py."""

    hits = scan_lines(
        patterns={
            "class_ProductContract": r"^\s*class\s+ProductContract\b",
        },
        allowlist_relpaths=(
            "contracts/product_contract.py",
            "tests/arch/test_lock_product_contract_single_source.py",
        ),
    )

    assert not hits, "ProductContract must be single-source-of-truth.\n" + format_hits(hits)
