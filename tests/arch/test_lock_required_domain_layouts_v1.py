from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REQUIRED = {
    "world_model": ["contracts.py", "types.py", "errors.py", "service.py", "guard.py"],
    "economics": ["contracts.py", "types.py", "errors.py", "service.py", "guard.py"],
    "simulation": ["contracts.py", "types.py", "errors.py", "service.py", "guard.py"],
    "knowledge": ["contracts.py", "types.py", "errors.py", "service.py", "guard.py"],
    "learning_loop": ["contracts.py", "types.py", "errors.py", "service.py", "guard.py"],
    "product": ["contracts.py", "types.py", "errors.py", "service.py", "guard.py"],
    "governance": ["contracts.py", "types.py", "errors.py", "service.py", "guard.py"],
    "finance": ["contracts.py", "types.py", "errors.py", "service.py", "guard.py"],
    "experiments": ["contracts.py", "types.py", "errors.py", "service.py", "guard.py"],
    "human_governance": ["contracts.py", "types.py", "errors.py", "service.py", "guard.py"],
}

def test_required_canon_domain_roots_exist_if_domain_exists() -> None:
    for name, files in REQUIRED.items():
        domain = ROOT / "core" / name
        if not domain.exists():
            continue
        for file_name in files:
            assert (domain / file_name).exists(), f"Missing required root file: core/{name}/{file_name}"
