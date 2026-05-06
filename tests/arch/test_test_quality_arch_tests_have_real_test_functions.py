from __future__ import annotations

from tests.arch._canon_test_quality_guard import arch_test_files, exempt, has_real_test_functions, parse_arch_test

def test_test_quality_arch_tests_have_real_test_functions() -> None:
    offenders=[]
    for path in arch_test_files():
        if exempt(path):
            continue
        parsed=parse_arch_test(path)
        if not has_real_test_functions(parsed):
            offenders.append(parsed.rel)
    assert not offenders, "Canonical arch-tests must define real test_* functions. Offenders:\n- " + "\n- ".join(offenders)
