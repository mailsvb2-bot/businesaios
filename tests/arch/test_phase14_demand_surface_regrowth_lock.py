from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

def test_no_retired_demand_transition_or_surface_tests_regrow() -> None:
    forbidden = [
        "tests/architecture/demand/test_no_pycache_or_build_artifacts.py",
        "tests/architecture/demand/test_demand_guardrails_transition_surface.py",
        "tests/architecture/demand/test_demand_economics_transition_surface.py",
        "tests/architecture/demand/test_marketplace_supply_directory_transition_surface.py",
        "tests/unit/demand/test_demand_guardrails_canonical_module.py",
        "tests/unit/demand/test_demand_economics_canonical_module.py",
        "tests/unit/demand/test_marketplace_supply_directory_surface.py",
    ]
    for rel in forbidden:
        assert not (PROJECT_ROOT / rel).exists(), rel

def test_canonical_demand_modules_still_exist() -> None:
    required = [
        "guardrails/demand_policies.py",
        "economics/demand_surface.py",
        "supply_directory/business_directory.py",
        "supply_directory/business_profile_store.py",
    ]
    for rel in required:
        assert (PROJECT_ROOT / rel).exists(), rel
