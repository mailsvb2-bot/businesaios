from __future__ import annotations

from pathlib import Path

from canon.namespace_aliases import CANONICAL_NAMESPACE_ALIASES
from canon.transition_surfaces import TRANSITION_SURFACE_MODULES

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_products_and_decision_namespaces_stay_transition_only() -> None:
    products_text = _read("core/products/__init__.py")
    assert "compatibility" in products_text.lower()
    assert "CANON_TRANSITION_SURFACE" in products_text

    decision_text = _read("core/decision/__init__.py")
    assert "CANON_TRANSITION_SURFACE" in decision_text


def test_namespace_alias_map_is_unique() -> None:
    values = list(CANONICAL_NAMESPACE_ALIASES.values())
    assert len(values) == len(set(values))


def test_core_products_namespace_contains_only_compatibility_shims() -> None:
    target = ROOT / "core" / "products"
    allowed = {"__init__.py", "product_contract_compat.py"}
    found = {path.name for path in target.rglob("*.py") if path.is_file()}
    unexpected = sorted(found - allowed)
    assert unexpected == [], unexpected


def test_transition_surfaces_do_not_expose_execution_or_decision_tokens() -> None:
    suspicious_tokens = (
        "def execute(",
        "def issue(",
        "def decide(",
        "final_action",
        "resolved_action",
    )
    offenders: list[str] = []
    for rel in TRANSITION_SURFACE_MODULES:
        text = _read(rel)
        for token in suspicious_tokens:
            if token in text:
                offenders.append(f"{rel}:{token}")
    assert not offenders, f"suspicious transition logic found: {offenders}"


def test_contract_aliases_point_to_single_source() -> None:
    import importlib

    from contracts.autopilot_contract import AutopilotContract as CanonicalAutopilotContract
    from contracts.product_contract import ProductContract as CanonicalProductContract

    CoreAutopilotContract = importlib.import_module("core.contracts.autopilot_contract").AutopilotContract
    CoreProductContract = importlib.import_module("core.contracts.product_contract").ProductContract
    LegacyProductContract = importlib.import_module("core.products.product_contract").ProductContract

    assert CoreProductContract is CanonicalProductContract
    assert LegacyProductContract is CanonicalProductContract
    assert CoreAutopilotContract is CanonicalAutopilotContract


def test_removed_legacy_modules_stay_absent() -> None:
    removed = (
        "core/policy/safe_rollout_legacy.py",
        "core/finance/contracts_legacy.py",
    )
    for rel in removed:
        assert not (ROOT / rel).exists(), f"Removed legacy module must stay absent: {rel}"


def test_hotspot_legacy_names_keep_explicit_canon_marker() -> None:
    targets = (
        "core/economics/brain.py",
        "core/economics/capital_engine.py",
        "core/economics/capital_allocation_engine.py",
        "core/growth/autopilot_engine.py",
        "runtime/handlers/ads_autopilot_flow.py",
    )
    offenders: list[str] = []
    for rel in targets:
        path = ROOT / rel
        if not path.exists():
            continue
        if "CANON_" not in path.read_text(encoding="utf-8"):
            offenders.append(rel)
    assert not offenders, (
        "Legacy hotspot files must contain explicit CANON marker until renamed. "
        f"Offenders: {offenders}"
    )
