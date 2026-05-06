from __future__ import annotations

from tools.canon_audit.registry import ManifestRegistry
from tools.canon_audit.score import CanonSubscores, compute_raw_score_100


def test_default_registry_has_unique_canonical_exports() -> None:
    registry = ManifestRegistry.from_default_manifests()
    duplicates = {k: v for k, v in registry.public_symbol_index().items() if len(v) > 1}
    assert duplicates == {}


def test_perfect_raw_score_budget_normalizes_to_100() -> None:
    score = compute_raw_score_100(
        CanonSubscores(
            functional_preservation=1.0,
            ownership_uniqueness=1.0,
            canonical_path_integrity=1.0,
            governance_integrity=1.0,
            evidence_integrity=1.0,
            runtime_discipline=1.0,
            proof_strength=1.0,
            duplicate_authority_penalty=0.0,
            hidden_logic_penalty=0.0,
            compatibility_penalty=0.0,
            god_module_penalty=0.0,
            alternative_route_penalty=0.0,
            fragility_penalty=0.0,
        )
    )
    assert score == 100.0
