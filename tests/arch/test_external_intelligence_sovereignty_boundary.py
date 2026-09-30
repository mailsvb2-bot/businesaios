from __future__ import annotations

import ast
from pathlib import Path

from application.business_autonomy.contracts import ExternalExecutionRequest

ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = ROOT / "application" / "business_autonomy" / "contracts.py"
SERVICE = ROOT / "application" / "business_autonomy" / "service.py"


def test_managed_external_request_has_no_business_goal_envelope_field() -> None:
    fields = set(ExternalExecutionRequest.__dataclass_fields__)
    assert "action_intent" in fields
    assert "envelope" not in fields
    assert "goal" not in fields
    assert "goal_payload" not in fields


def test_managed_service_never_falls_back_to_goal_level_execute() -> None:
    tree = ast.parse(SERVICE.read_text(encoding="utf-8"), filename=str(SERVICE))
    source = SERVICE.read_text(encoding="utf-8")
    assert "managed_intent_boundary_unsupported" in source
    assert "missing_action_intent" in source
    managed_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "execute_intent"
    ]
    assert managed_calls


def test_external_execution_contract_owner_reuses_action_intent_v2() -> None:
    tree = ast.parse(CONTRACTS.read_text(encoding="utf-8"), filename=str(CONTRACTS))
    external = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "ExternalExecutionRequest"
    )
    annotations = {
        node.target.id: ast.unparse(node.annotation)
        for node in external.body
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
    }
    assert annotations["action_intent"] == "ActionIntentV2"



def test_managed_boundary_revalidates_intent_integrity_before_external_effect() -> None:
    source = SERVICE.read_text(encoding="utf-8")
    assert "canonical_payload_hash(intent.parameters_copy()) != intent.payload_hash" in source
    assert "intent.correlation_id != delegated_request.correlation_id" in source


def test_managed_external_outputs_are_explicitly_non_authoritative() -> None:
    source = SERVICE.read_text(encoding="utf-8")
    assert '"external_output_role": "execution_result_evidence"' in source
    assert '"decision_authority": False' in source
