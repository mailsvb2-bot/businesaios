from __future__ import annotations

from pathlib import Path
from typing import List

from .constants import DOMAIN_OPTIONAL_ROOT_FILES, OPTIONAL_ROOT_FILES, REQUIRED_ROOT_FILES
from .domain_discovery import is_transient_path, rel
from .findings import CanonFsFinding


def scan_domain_root(root: Path, domain: Path) -> List[CanonFsFinding]:
    findings: List[CanonFsFinding] = []
    names = {p.name for p in domain.iterdir() if not is_transient_path(p)}
    domain_optional = set(DOMAIN_OPTIONAL_ROOT_FILES.get(domain.name, ()))

    for required in REQUIRED_ROOT_FILES:
        if required not in names:
            findings.append(
                CanonFsFinding(
                    path=rel(root, domain / required),
                    kind="missing-required-domain-root-file",
                    message=f"Required canon root file missing: {required}",
                )
            )

    for path in domain.glob("*.py"):
        if path.name not in REQUIRED_ROOT_FILES and path.name not in OPTIONAL_ROOT_FILES and path.name not in domain_optional:
            findings.append(
                CanonFsFinding(
                    path=rel(root, path),
                    kind="unexpected-domain-root-file",
                    message=(
                        "Unexpected python file in canon domain root. "
                        "Move logic into allowed root files or role folders."
                    ),
                )
            )

    return findings
