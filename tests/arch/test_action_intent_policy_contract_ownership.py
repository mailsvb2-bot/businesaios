from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

SEMANTIC_CLASS_OWNERS = {
    "Decision": Path("contracts/decisioning/sovereign_decision_contract.py"),
    "DecisionEnvelope": Path("contracts/decisioning/sovereign_decision_contract.py"),
    "WorldStateV1": Path("kernel/world_state.py"),
    "BusinessFactV1": Path("contracts/event_store.py"),
    "ActionIntentV1": Path("contracts/action_intent.py"),
    "PolicyDecisionV1": Path("contracts/policy_decision.py"),
    "ExecutableAction": Path("contracts/executable_action.py"),
    "BusinessOutcomeV1": Path("contracts/business_outcome.py"),
    "Customer": Path("contracts/customer.py"),
    "CustomerIdentity": Path("contracts/customer.py"),
    "CustomerTimeline": Path("contracts/customer.py"),
    "CustomerRegistry": Path("crm/customer_registry.py"),
    "CustomerTimelineProjector": Path("crm/customer_timeline.py"),
}
_SEMANTIC_CLASS_NAMES = frozenset(SEMANTIC_CLASS_OWNERS)


def _class_definitions() -> dict[str, list[Path]]:
    definitions = {name: [] for name in SEMANTIC_CLASS_OWNERS}
    for path in ROOT.rglob("*.py"):
        rel = path.relative_to(ROOT)
        if "tests" in rel.parts or ".git" in rel.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if not any(name in text for name in _SEMANTIC_CLASS_NAMES):
            continue
        tree = ast.parse(text, filename=str(rel))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name in definitions:
                definitions[node.name].append(rel)
    return definitions


def semantic_contract_owner_mismatches() -> dict[str, tuple[list[Path], list[Path]]]:
    actual = _class_definitions()
    expected = {name: [owner] for name, owner in SEMANTIC_CLASS_OWNERS.items()}
    return {
        name: (actual[name], expected[name])
        for name in SEMANTIC_CLASS_OWNERS
        if actual[name] != expected[name]
    }


def test_new_semantic_contracts_have_one_physical_owner() -> None:
    assert not semantic_contract_owner_mismatches()


def test_compatibility_surfaces_preserve_owner_identity() -> None:
    from application.autonomy.autonomy_tiers import AutonomyDecision
    from contracts.decisioning.decision_context_projection import DecisionContextProjection
    from contracts.decisioning.sovereign_decision_contract import Decision, DecisionEnvelope
    from contracts.decisioning.world_state_contract import WorldStateContract
    from contracts.event_store import AppendEvent, EventAppendProtocol, normalize_append_event
    from contracts.policy_decision import PolicyDecisionV1
    from core.ai.decision_contracts import Decision as CoreDecision
    from core.ai.decision_contracts import DecisionEnvelope as CoreDecisionEnvelope
    from runtime.platform.event_store.append_contract import AppendEvent as RuntimeAppendEvent
    from runtime.platform.event_store.append_contract import EventAppendProtocol as RuntimeEventAppendProtocol
    from runtime.platform.event_store.append_contract import normalize_append_event as runtime_normalize_append_event

    assert CoreDecision is Decision
    assert CoreDecisionEnvelope is DecisionEnvelope
    assert WorldStateContract is DecisionContextProjection
    assert AutonomyDecision is PolicyDecisionV1
    assert RuntimeAppendEvent is AppendEvent
    assert RuntimeEventAppendProtocol is EventAppendProtocol
    assert runtime_normalize_append_event is normalize_append_event


def test_new_contract_owners_remain_declared_by_canon() -> None:
    role = (ROOT / "contracts/CANON_NAMESPACE_ROLE.md").read_text(encoding="utf-8")
    for name in ("BusinessFactV1", "ActionIntentV1", "PolicyDecisionV1", "BusinessOutcomeV1", "Customer", "CustomerIdentity", "CustomerTimeline"):
        assert name in role
    assert "kernel.world_state.WorldStateV1" in role
    assert "contracts/decisioning/sovereign_decision_contract.py" in role


def test_decision_core_remains_the_only_intent_projection_owner() -> None:
    autonomy = (ROOT / "application/autonomy/autonomy_tiers.py").read_text(encoding="utf-8")
    decision_core = (ROOT / "core/ai/decision_core.py").read_text(encoding="utf-8")
    assert "class AutonomyDecision" not in autonomy
    assert "AutonomyDecision = PolicyDecisionV1" in autonomy
    assert "def project_action_intent(" in decision_core
    assert "ExecutableAction(" in decision_core


def test_customer_runtime_extends_existing_owners_without_second_semantic_store() -> None:
    registry = (ROOT / "crm/customer_registry.py").read_text(encoding="utf-8")
    timeline = (ROOT / "crm/customer_timeline.py").read_text(encoding="utf-8")
    bootstrap = (ROOT / "runtime/business_autonomy/bootstrap.py").read_text(encoding="utf-8")
    router = (ROOT / "adapters/api/fastapi/router_adapter.py").read_text(encoding="utf-8")
    provider_admin = (ROOT / "application/business_autonomy/provider_admin_service.py").read_text(encoding="utf-8")
    assert "BusinessFactV1(" in registry
    assert "build_idempotency_key(" in registry
    assert "SecretVault" in registry
    assert "CustomerRegistry(event_store=customer_event_store, idempotency_store=distributed['idempotency'], pii_vault=secret_vault)" in bootstrap
    assert "customer_event_store=getattr(runtime_infra, 'event_store', None)" in router
    assert "customer_registry=self.customer_registry" in provider_admin
    assert "append_event(" not in timeline
    assert "IdempotencyStore" not in timeline
    assert "CustomerTimelineProjector" in timeline
