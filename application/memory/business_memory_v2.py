from __future__ import annotations

from dataclasses import asdict
from typing import Any

from application.memory.business_operating_memory import BusinessOperatingMemory

CANON_BUSINESS_MEMORY_V2 = True
MEMORY_LIFECYCLE = ("create", "validate", "refresh", "supersede", "expire", "archive", "forget")


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
    edges = [
        {"from": f"business:{memory.business_id}", "to": node["id"], "relation": "has_memory"}
        for node in nodes[1:]
    ]
    return {"projection_only": True, "source_of_truth": False, "scope": view["scope"], "nodes": nodes, "edges": edges}


__all__ = ["CANON_BUSINESS_MEMORY_V2", "MEMORY_LIFECYCLE", "project_business_memory_v2", "project_memory_knowledge_graph"]
