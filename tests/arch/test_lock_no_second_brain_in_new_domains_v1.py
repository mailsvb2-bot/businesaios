from __future__ import annotations
from pathlib import Path
from canon.domain_fs import scan_canon_domain_file_system
ROOT = Path(__file__).resolve().parents[2]

def test_new_canon_domains_have_no_second_brain_paths() -> None:
    findings = [item for item in scan_canon_domain_file_system(ROOT) if item.kind == "second-brain-path-detected"]
    assert findings == [], [f"{item.kind}:{item.path}:{item.message}" for item in findings]
