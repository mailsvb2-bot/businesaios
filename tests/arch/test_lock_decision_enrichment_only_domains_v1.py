from __future__ import annotations

from pathlib import Path

from canon.domain_fs import scan_canon_domain_file_system


ROOT = Path(__file__).resolve().parents[2]


def test_canon_domains_are_enrichment_only_not_issuers() -> None:
    findings = [
        item
        for item in scan_canon_domain_file_system(ROOT)
        if item.kind == "second-brain-path-detected"
    ]
    assert findings == [], [f"{i.kind}:{i.path}:{i.message}" for i in findings]
