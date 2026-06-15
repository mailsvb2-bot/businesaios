from __future__ import annotations

from scripts.ci.step_integrity_cargo_tests import _executed_test_count


def test_executed_test_count_handles_multiple_cargo_sections() -> None:
    output = """
running 3 tests
test a ... ok
test b ... ok
test c ... ok

Doc-tests businessaios_integrity_core

running 0 tests
"""

    assert _executed_test_count(output) == 3


def test_executed_test_count_handles_single_test_grammar() -> None:
    assert _executed_test_count("running 1 test") == 1
