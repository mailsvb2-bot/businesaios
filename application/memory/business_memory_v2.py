from __future__ import annotations

from dataclasses import asdict, replace
from typing import Any

from application.memory.business_operating_memory import BusinessOperatingMemory
from application.memory.business_operating_memory_types import DurableMemoryRecord

CANON_BUSINESS_MEMORY_V2 = True
MEMORY_LIFECYCLE = ("create", "validate", "refresh", "supersede", "expire", "archive", "forget")
_ACTIVE_MEMORY_STATES = frozenset({"validate", "refresh"})
_ALLOWED_TRANSITIONS = {
    "create": frozenset({"validate", "forget"}),
    "validate": frozenset({"refresh", "supersede", "expire", "archive", "forget"}),
    "refresh": frozenset({"refresh", "supersede", "expire", "archive", "forget"}),
    "supersede": frozenset({"archive", "forget"}),
    "expire": frozenset({"archive", "forget"}),
    "archive": frozenset({"forget"}),
    "forget": frozenset(),
}


def add_memory_candidate(memory: BusinessOperatingMemory, record: DurableMemoryRecord) -> BusinessOperatingMemory:
    if record.status != "create":
        raise ValueError("new memory candidate must start in create state")
    if not record.memory_id or not record.key:
        raise ValueError("memory candidate requires memory_id and key")
    existing = next((item for item in memory.durable_memory if item.memory_id == record.memory_id), None)
    if existing is not None:
        if existing == record:
            return memory
        raise ValueError("memory_id collision")
    return replace(memory, durable_memory=(record, *memory.durable_memory))


def transition_memory(
    memory: BusinessOperatingMemory,
    *,
    memory_id: str,
    transition: str,
    provenance: tuple[str, ...] = (),
    updated_at: str | None = None,
) -> BusinessOperatingMemory:
    action = str(transition or "").strip()
    rows = list(memory.durable_memory)
    index = next((i for i, item in enumerate(rows) if item.memory_id == memory_id), None)
    if index is None:
        raise KeyError(memory_id)
    current = rows[index]
    if action not in _ALLOWED_TRANSITIONS.get(current.status, frozenset()):
        raise ValueError(f"invalid memory transition: {current.status}->{action}")
    evidence = tuple(dict.fromkeys((*current.provenance, *provenance)))
    if action in {"validate", "refresh"} and not evidence:
        raise ValueError("validated durable memory requires provenance")
    rows[index] = replace(
        current,
        status=action,
        provenance=() if action == "forget" else evidence,
        value="" if action == "forget" else current.value,
        updated_at=updated_at or current.updated_at,
    )
    return replace(memory, durable_memory=tuple(rows))


def project_portable_memory(memory: BusinessOperatingMemory, *, allow_global: bool = False) -> list[dict[str, Any]]:
    if not allow_global:
        return []
    return [
        {"memory_type": row.memory_type, "key": row.key, "value": row.value, "confidence": row.confidence, "sample_size": row.sample_size}
        for row in memory.durable_memory
        if row.status in _ACTIVE_MEMORY_STATES and row.portable and row.anonymized
    ]


def project_business_memory_v2(memory: BusinessOperatingMemory) -> dict[str, Any]:
    scope = {"tenant_id": memory.tenant_id, "business_id": memory.business_id}
    procedural = []
    for kind, rows in (
        ("success_pattern", memory.recurring_wins),
        ("failure_pattern", memory.recurring_failures),
        ("anti_pattern", memory.anti_patterns),
    ):
        for item in rows:
            data = asdict(item)
            procedural.append({
                "kind": kind,
                "key": data.get("key", ""),
                "evidence": list(data.get("source_run_ids") or []),
                "sample_size": int(data.get("count") or len(data.get("source_run_ids") or [])),
                "scope": scope,
                "confidence": float(data.get("confidence") or 0.0),
                "freshness": float(data.get("freshness") or 0.0),
            })
    strategic = [
        {
            "run_id": run.run_id,
            "tried": run.summary,
            "why": run.goal,
            "conditions": dict(run.fingerprint),
            "result": "completed" if run.completed else run.stop_reason,
            "why_abandoned": "" if run.completed else run.stop_reason,
            "recorded_at": run.recorded_at,
        }
        for run in memory.recent_runs
    ]
    evidence_refs = sorted({
        ref
        for item in procedural
        for ref in list(item.get("evidence") or [])
        if str(ref).strip()
    })
    durable = [asdict(row) for row in memory.durable_memory if row.status in _ACTIVE_MEMORY_STATES]
    return {
        "schema_version": 2,
        "scope": scope,
        "operational_state": {"owner": "WorldModel", "stored_here": False},
        "episodic_memory": [asdict(run) for run in memory.recent_runs],
        "semantic_memory": {
            "business_profile": dict(memory.business_profile),
            "signals": [asdict(item) for item in memory.signal_memory],
            "trends": None if memory.trends is None else asdict(memory.trends),
        },
        "procedural_memory": procedural,
        "business_preferences": dict(memory.learned_preferences),
        "durable_memory": durable,
        "evidence_store": {"owner": "EvidenceStore", "stored_here": False, "refs": evidence_refs},
        "strategic_memory": strategic,
        "lifecycle": list(MEMORY_LIFECYCLE),
        "evidence_only": True,
        "must_not_issue_decision": True,
        "must_not_unlock_effects": True,
    }


def project_memory_knowledge_graph(memory: BusinessOperatingMemory) -> dict[str, Any]:
    view = project_business_memory_v2(memory)
    nodes = [{"id": f"business:{memory.business_id}", "kind": "business"}]
    nodes.extend({"id": f"procedure:{row['kind']}:{row['key']}", "kind": row["kind"]} for row in view["procedural_memory"])
    nodes.extend({"id": f"memory:{row['memory_id']}", "kind": row["memory_type"]} for row in view["durable_memory"])
    edges = [
        {"from": f"business:{memory.business_id}", "to": node["id"], "relation": "has_memory"}
        for node in nodes[1:]
    ]
    return {"projection_only": True, "source_of_truth": False, "scope": view["scope"], "nodes": nodes, "edges": edges}


__all__ = [
    "CANON_BUSINESS_MEMORY_V2", "MEMORY_LIFECYCLE", "add_memory_candidate", "transition_memory",
    "project_business_memory_v2", "project_memory_knowledge_graph", "project_portable_memory",
]
