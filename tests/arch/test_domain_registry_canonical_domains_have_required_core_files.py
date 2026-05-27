from __future__ import annotations

from tests.arch._canon_domain_registry_guard import domain_info_list, missing_required_files


def test_domain_registry_canonical_domains_have_required_core_files() -> None:
    offenders: list[str] = []
    for domain in domain_info_list():
        missing = missing_required_files(domain)
        if missing:
            offenders.append(f"{domain.rel}: missing {', '.join(missing)}")
    assert not offenders, "Canonical core domains must provide contracts.py, types.py, errors.py, service.py. Offenders:\n- " + "\n- ".join(offenders)
