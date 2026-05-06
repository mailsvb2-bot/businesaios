from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_twenty_duplicate_hotspots_stay_locked_to_single_canonical_owner() -> None:
    file_locks = {
        1: ("demand_guardrails/demand_decision_guard.py", "guardrails/demand_policies.py"),
        2: ("demand_guardrails/fraud_pattern_guard.py", "guardrails/demand_policies.py"),
        3: ("demand_guardrails/routing_risk_guard.py", "guardrails/demand_policies.py"),
        4: ("demand_guardrails/rollback_guard.py", "guardrails/demand_policies.py"),
        5: ("demand_guardrails/customer_fit_guard.py", "guardrails/demand_policies.py"),
        6: ("demand_guardrails/no_monopoly_guard.py", "guardrails/demand_policies.py"),
        7: ("demand_economics/business_ltv_by_route.py", "economics.demand_surface"),
        8: ("demand_economics/channel_mix_profitability.py", "economics.demand_surface"),
        9: ("demand_economics/customer_acquisition_cost_by_channel.py", "economics.demand_surface"),
        10: ("demand_economics/demand_margin_snapshot.py", "economics.demand_surface"),
        11: ("demand_economics/lead_unit_economics.py", "economics.demand_surface"),
        12: ("demand_economics/marketplace_take_rate.py", "economics.demand_surface"),
        13: ("demand_economics/routed_lead_value.py", "economics.demand_surface"),
        14: ("demand_economics/routing_profitability_engine.py", "economics.demand_surface"),
        20: ("demand_seo/location_page_generator.py", "growth.seo.location_page_generator"),
    }
    for _, (rel, canonical) in file_locks.items():
        text = _read(rel)
        assert canonical in text, f"{rel} must point to canonical owner {canonical}"

    alias_locks = {
        15: ("marketplace/__init__.py", "supply_directory.business_directory"),
        16: ("marketplace/__init__.py", "supply_directory.business_profile_store"),
        17: ("registry/__init__.py", "shared.registry"),
        18: ("registry/__init__.py", "shared.registry"),
        19: ("registry/__init__.py", "shared.registry"),
    }
    for _, (rel, canonical) in alias_locks.items():
        text = _read(rel)
        assert canonical in text, f"{rel} must point to canonical owner {canonical}"
