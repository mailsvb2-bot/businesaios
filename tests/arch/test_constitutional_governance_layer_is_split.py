from pathlib import Path


def test_constitutional_governance_layer_is_split() -> None:
    for rel in (
        "infra/decision_rights_registry.py",
        "infra/authority_scopes.py",
        "infra/policy_constitution.py",
        "infra/forbidden_operator_actions.py",
        "infra/escalation_routes.py",
        "infra/governance_invariants.py",
        "infra/constitutional_governance_service.py",
        "infra/constitutional_governance_boot.py",
        "infra/constitutional_governance_boot_result.py",
    ):
        assert Path(rel).exists(), rel
