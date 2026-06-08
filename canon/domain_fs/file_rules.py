from __future__ import annotations

from pathlib import Path

from .constants import (
    FORBIDDEN_FILENAME_STEMS,
    FORBIDDEN_SECOND_BRAIN_PATTERNS,
    ROOT_FILE_LINE_LIMITS,
)
from .domain_discovery import is_transient_path, line_count, read_text_safe, rel
from .findings import CanonFsFinding


def scan_domain_files(root: Path, domain: Path) -> list[CanonFsFinding]:
    findings: list[CanonFsFinding] = []

    for path in domain.rglob("*.py"):
        if is_transient_path(path):
            continue
        rel_path = rel(root, path)
        text = read_text_safe(path)
        stem = path.stem.lower()

        for token in FORBIDDEN_FILENAME_STEMS:
            if token in stem and path.name != "__canon_domain__.py":
                findings.append(
                    CanonFsFinding(
                        path=rel_path,
                        kind="forbidden-role-name",
                        message=f"Forbidden fuzzy role in canon domain file name: {token}",
                    )
                )

        for token in FORBIDDEN_SECOND_BRAIN_PATTERNS:
            if token in text:
                findings.append(
                    CanonFsFinding(
                        path=rel_path,
                        kind="second-brain-path-detected",
                        message=f"Forbidden second-brain/direct-apply token detected: {token}",
                    )
                )

        limit = ROOT_FILE_LINE_LIMITS.get(path.name)
        if limit is not None and line_count(path) > limit:
            findings.append(
                CanonFsFinding(
                    path=rel_path,
                    kind="canon-root-file-too-large",
                    message=f"{path.name} exceeds line limit {limit}. Split logic into role folders.",
                )
            )

    return findings
