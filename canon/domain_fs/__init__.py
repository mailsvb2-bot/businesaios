from __future__ import annotations

from pathlib import Path
from collections.abc import Iterable

from .boot_rules import scan_boot_wiring_only
from .constants import (
    ALLOWED_SUBDIRS,
    BOOT_WIRING_LINE_LIMIT,
    CANON_DOMAIN_MARKER,
    DOMAIN_FILE_SYSTEM_VERSION,
    FORBIDDEN_FILENAME_STEMS,
    FORBIDDEN_ROLE_NAMES,
    LEGACY_RELAXED_DOMAINS,
    REQUIRED_ROOT_FILES,
    STRATEGIC_DOMAIN_NAMES,
    THIN_HANDLER_LINE_LIMIT,
)
from .domain_discovery import iter_canon_domains
from .file_rules import scan_domain_files
from .findings import CanonFsFinding
from .root_rules import scan_domain_root
from .runtime_rules import scan_thin_runtime_handlers
from .subdir_rules import scan_domain_subdirs


def scan_canon_domain_file_system(repo_root: str | Path) -> list[CanonFsFinding]:
    root = Path(repo_root)
    findings: list[CanonFsFinding] = []

    for domain in iter_canon_domains(root):
        if domain.name in LEGACY_RELAXED_DOMAINS:
            continue
        findings.extend(scan_domain_root(root, domain))
        findings.extend(scan_domain_subdirs(root, domain))
        findings.extend(scan_domain_files(root, domain))

    return findings


def findings_as_dicts(items: Iterable[CanonFsFinding]) -> list[dict]:
    return [{"path": i.path, "kind": i.kind, "message": i.message} for i in items]


__all__ = [
    "ALLOWED_SUBDIRS",
    "BOOT_WIRING_LINE_LIMIT",
    "CANON_DOMAIN_MARKER",
    "DOMAIN_FILE_SYSTEM_VERSION",
    "FORBIDDEN_FILENAME_STEMS",
    "FORBIDDEN_ROLE_NAMES",
    "REQUIRED_ROOT_FILES",
    "STRATEGIC_DOMAIN_NAMES",
    "THIN_HANDLER_LINE_LIMIT",
    "findings_as_dicts",
    "scan_boot_wiring_only",
    "scan_canon_domain_file_system",
    "scan_thin_runtime_handlers",
]
