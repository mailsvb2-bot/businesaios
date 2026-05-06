from __future__ import annotations

from tests.arch._canon_test_quality_guard import arch_test_files, exempt, is_import_only_like, parse_arch_test

def test_test_quality_no_import_only_pseudo_tests() -> None:
    offenders=[]
    for path in arch_test_files():
        if exempt(path):
            continue
        parsed=parse_arch_test(path)
        if is_import_only_like(parsed):
            offenders.append(parsed.rel)
    assert not offenders, "Canonical arch-tests must not degrade into import-only pseudo-tests. Offenders:\n- " + "\n- ".join(offenders)
