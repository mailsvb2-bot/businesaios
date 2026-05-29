from __future__ import annotations

from pathlib import Path

import pytest

from runtime.platform.support.tests.arch.scaffold_assertions import assert_arch_scaffold
from runtime.platform.support.tests.scaffold_manifest import SCAFFOLD_CASES


@pytest.mark.parametrize("relative_path", SCAFFOLD_CASES)
def test_support_scaffold_manifest_entry(relative_path: str) -> None:
    pseudo_path = Path(__file__).resolve().parent / relative_path
    assert pseudo_path.suffix == ".py"
    assert pseudo_path.name.startswith("test_")
    assert pseudo_path.parent.name in {
        "arch",
        "chaos",
        "e2e",
        "integration",
        "load",
        "regression",
        "reproducibility",
        "unit",
    }


def test_support_scaffold_manifest_is_unique_and_sorted() -> None:
    assert sorted(SCAFFOLD_CASES) == SCAFFOLD_CASES
    assert len(SCAFFOLD_CASES) == len(set(SCAFFOLD_CASES))


def test_support_scaffold_suite_is_real_test() -> None:
    assert_arch_scaffold(__file__)

__all__ = [
    "SCAFFOLD_CASES",
    "test_support_scaffold_manifest_entry",
    "test_support_scaffold_manifest_is_unique_and_sorted",
    "test_support_scaffold_suite_is_real_test",
]
