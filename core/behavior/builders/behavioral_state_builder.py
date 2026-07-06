from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.behavior.adapters.decisioncore_adapter import build_decisioncore_behavior_payload
from core.behavior.assemblers.org_field_assembler import assemble_org_field
from core.behavior.assemblers.person_field_assembler import assemble_person_field
from core.behavior.builders.base_spinor_factory import spinor_from_scores
from core.behavior.contracts.micro_spinor import MicroSpinor
from core.behavior.contracts.person_field import PersonField
from core.behavior.observables.org_observables import compute_org_observables
from core.behavior.operators.dirac_operator_service import DiracOperatorService
from core.behavior.operators.operator_context_resolver import resolve_operator_runtime_context
from core.behavior.operators.operator_denials import PolicyDenials


def build_behavioral_state(
    entity_id: str,
    events: list[Mapping[str, Any]],
    *,
    catalog_root: Path,
    policy_root: Path,
) -> dict[str, object]:
    service = DiracOperatorService(catalog_root, policy_root)
    denials = PolicyDenials()
    micro_spinors: list[MicroSpinor] = []
    psi = spinor_from_scores(0.4, 0.4, 0.4, 0.3)

    for index, event in enumerate(events):
        ctx = resolve_operator_runtime_context(event)
        operator_key = str(event.get("event_type", "message_open"))
        psi = service.apply(psi, operator_key, ctx, denials)
        ts = event.get("timestamp")
        if not isinstance(ts, datetime):
            ts = datetime.now(UTC)
        micro_spinors.append(
            MicroSpinor(
                spinor_id=f"stream:{entity_id}:{index}",
                entity_id=entity_id,
                scope_type="stream",
                scope_ref=operator_key,
                started_at=ts,
                ended_at=ts,
                psi_re=psi.re,
                psi_im=psi.im,
                amplitude=psi.magnitude(),
                phase=psi.phase(),
                source_event_refs=(str(event.get("event_id", index)),),
                operator_trace=(operator_key,),
                context=dict(event),
            )
        )

    person_field = assemble_person_field(entity_id, micro_spinors)
    payload = build_decisioncore_behavior_payload(person_field.dynamic_observables, policy_denials=denials.total())
    payload["behavior"]["policy_denials"] = dict(denials.counts)
    return {
        "entity_id": entity_id,
        "person_field": person_field,
        "payload": payload,
    }


def build_org_behavioral_state(
    org_id: str,
    role_events: Mapping[str, list[Mapping[str, Any]]],
    *,
    catalog_root: Path,
    policy_root: Path,
) -> dict[str, object]:
    role_fields: dict[str, PersonField] = {}
    total_denials = 0
    for role, events in role_events.items():
        state = build_behavioral_state(f"{org_id}:{role}", events, catalog_root=catalog_root, policy_root=policy_root)
        role_fields[role] = state["person_field"]
        payload = state["payload"]
        total_denials += len(payload["behavior"].get("policy_denials", {}))
    org_field = assemble_org_field(org_id, role_fields)
    behavior_payload = build_decisioncore_behavior_payload(org_field.observables, policy_denials=total_denials)
    behavior_payload["behavior"]["org_observables"] = compute_org_observables(role_fields)
    return {
        "org_id": org_id,
        "org_field": org_field,
        "payload": behavior_payload,
    }
