from __future__ import annotations

from pathlib import Path

from canon.domain_fs import scan_canon_domain_file_system

ROOT = Path(__file__).resolve().parents[1]


def test_governance_domain_is_now_dfs_v1_opted_in() -> None:
    marker = ROOT / "core" / "governance" / "__canon_domain__.py"
    assert marker.exists()
    findings = [item for item in scan_canon_domain_file_system(ROOT) if item.path.startswith("core/governance/")]
    assert findings == [], [f"{item.kind}:{item.path}" for item in findings]
