from __future__ import annotations

from tests.arch._canon_domain_registry_guard import domain_has_any_python, domain_info_list

def test_domain_registry_canonical_domains_are_not_empty() -> None:
    offenders: list[str] = []
    for domain in domain_info_list():
        if not domain_has_any_python(domain):
            offenders.append(domain.rel)
    assert not offenders, "Canonical domains must not be empty. Offenders:\n- " + "\n- ".join(offenders)
