from __future__ import annotations

from pathlib import Path
from typing import List

from .constants import ALLOWED_SUBDIRS
from .domain_discovery import is_transient_path, rel
from .findings import CanonFsFinding


def scan_domain_subdirs(root: Path, domain: Path) -> list[CanonFsFinding]:
    findings: list[CanonFsFinding] = []

    for child in domain.iterdir():
        if child.is_dir() and not is_transient_path(child) and child.name not in ALLOWED_SUBDIRS:
            findings.append(
                CanonFsFinding(
                    path=rel(root, child),
                    kind="unexpected-domain-subdir",
                    message=f"Unexpected subdirectory in canon strategic domain: {child.name}",
                )
            )

    return findings
