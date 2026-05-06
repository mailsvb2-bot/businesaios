from __future__ import annotations
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def test_extended_canon_domains_have_required_roots() -> None:
    for domain in ("product", "finance", "experiments", "human_governance"):
        base = ROOT / "core" / domain
        assert (base / "__canon_domain__.py").exists()
        for name in ("contracts.py", "types.py", "errors.py", "service.py", "guard.py"):
            assert (base / name).exists(), f"missing {domain}/{name}"

def test_governance_domain_is_now_opted_in() -> None:
    base = ROOT / "core" / "governance"
    assert (base / "contracts.py").exists()
    assert (base / "service.py").exists()
    assert (base / "__canon_domain__.py").exists()
