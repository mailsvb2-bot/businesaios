from __future__ import annotations

from tests.arch._canon_test_quality_guard import arch_test_files, exempt, parse_arch_test, suspiciously_short


def test_test_quality_arch_tests_not_suspiciously_short() -> None:
    offenders=[]
    for path in arch_test_files():
        if exempt(path):
            continue
        parsed=parse_arch_test(path)
        if suspiciously_short(parsed):
            offenders.append(parsed.rel)
    assert not offenders, "Canonical arch-tests are suspiciously short. Offenders:\n- " + "\n- ".join(offenders)
