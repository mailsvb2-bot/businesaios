from __future__ import annotations

from tests.arch._canon_test_quality_guard import arch_test_files, exempt, has_quality_signal, parse_arch_test


def test_test_quality_arch_tests_have_quality_signals() -> None:
    offenders=[]
    for path in arch_test_files():
        if exempt(path):
            continue
        parsed=parse_arch_test(path)
        if not has_quality_signal(parsed):
            offenders.append(parsed.rel)
    assert not offenders, "Canonical arch-tests should use AST/import/path/helper quality signals. Offenders:\n- " + "\n- ".join(offenders)
