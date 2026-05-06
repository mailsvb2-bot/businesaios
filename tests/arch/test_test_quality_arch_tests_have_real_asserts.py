from __future__ import annotations

from tests.arch._canon_test_quality_guard import arch_test_files, assertion_count, exempt, parse_arch_test

def test_test_quality_arch_tests_have_real_asserts() -> None:
    offenders=[]
    for path in arch_test_files():
        if exempt(path):
            continue
        parsed=parse_arch_test(path)
        if assertion_count(parsed.tree) == 0:
            offenders.append(parsed.rel)
    assert not offenders, "Canonical arch-tests must contain real assert statements. Offenders:\n- " + "\n- ".join(offenders)
