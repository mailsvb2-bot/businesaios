from __future__ import annotations

from tests.arch._canon_test_quality_guard import arch_test_files, exempt, has_forbidden_snippet, parse_arch_test


def test_test_quality_no_placeholder_or_decorative_markers() -> None:
    offenders=[]
    for path in arch_test_files():
        if exempt(path):
            continue
        parsed=parse_arch_test(path)
        if has_forbidden_snippet(parsed):
            offenders.append(parsed.rel)
    assert not offenders, "Canonical arch-tests must not contain placeholder/decorative markers. Offenders:\n- " + "\n- ".join(offenders)
