from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping

from config.execution_contract import CANONICAL_DECISION_PATH, CANONICAL_OPTIMIZATION_TARGET
from demand_decision.canonical_decision_bridge import CanonicalDemandDecisionBridge

from .canonical_observation import canonicalize_mapping
from .differential import compare_contracts
from .golden_trace import compare_traces
from .replay_runtime import replay_runtime_decision

@dataclass(frozen=True)
class ProjectSnapshotCase:
    name: str
    scenario_type: str
    payload: dict[str, Any]
    expected_contract: dict[str, Any]
    expected_trace: dict[str, Any]

class _RejectingDecisionCore:
    def evaluate(self, *_args: Any, **_kwargs: Any) -> tuple[SimpleNamespace, dict[str, Any]]:
        return SimpleNamespace(candidate=None, trace=SimpleNamespace(decision_id="snapshot-reject")), {}
    decide = evaluate

class _SelectingDecisionCore:
    def __init__(self, *, selected_business_id: str, delivery_channel: str) -> None:
        self._selected_business_id = selected_business_id
        self._delivery_channel = delivery_channel

    def evaluate(self, decision_space: Any, *_args: Any, **_kwargs: Any) -> tuple[SimpleNamespace, dict[str, Any]]:
        for candidate in getattr(decision_space, "candidates", ()):
            business_id = str(candidate.payload.get("business_id") or "").strip()
            if business_id == self._selected_business_id:
                return SimpleNamespace(candidate=candidate, trace=SimpleNamespace(decision_id="snapshot-allow")), {}
        return SimpleNamespace(candidate=None, trace=SimpleNamespace(decision_id="snapshot-miss")), {}
    decide = evaluate

class _RoutingCandidate:
    def __init__(self, business_id: str, rank_score: float, *, blocked: bool = False, trace: Mapping[str, Any] | None = None) -> None:
        self.business_id = business_id
        self.rank_score = rank_score
        self.blocked = blocked
        self.trace = dict(trace or {"adjusted_score": rank_score, "match_score": rank_score})

class _Request:
    def __init__(self, request_id: str, customer_id: str = "cust-snapshot") -> None:
        self.request_id = request_id
        self.customer_id = customer_id

def _bundle_root() -> Path:
    return Path(__file__).resolve().parent / "fixtures" / "project_snapshot_bundle"

def load_project_snapshot_bundle(root: Path | None = None) -> list[ProjectSnapshotCase]:
    base = root or _bundle_root()
    cases: list[ProjectSnapshotCase] = []
    for path in sorted(base.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        cases.append(
            ProjectSnapshotCase(
                name=payload["name"],
                scenario_type=payload["scenario_type"],
                payload=payload["payload"],
                expected_contract=payload["expected_contract"],
                expected_trace=payload["expected_trace"],
            )
        )
    return cases

def summarize_project_snapshot_bundle(root: Path | None = None) -> dict[str, Any]:
    cases = load_project_snapshot_bundle(root)
    return {
        "count": len(cases),
        "names": tuple(case.name for case in cases),
        "scenario_types": tuple(sorted({case.scenario_type for case in cases})),
        "ok": bool(cases),
    }

def _run_runtime_case(payload: Mapping[str, Any]) -> dict[str, Any]:
    return dict(replay_runtime_decision(payload))

def _build_bridge(scenario: Mapping[str, Any]) -> CanonicalDemandDecisionBridge:
    mode = str(scenario.get("mode") or "reject")
    if mode == "select":
        return CanonicalDemandDecisionBridge(
            decision_core=_SelectingDecisionCore(
                selected_business_id=str(scenario.get("selected_business_id") or ""),
                delivery_channel=str(scenario.get("delivery_channel") or "telegram"),
            )
        )
    return CanonicalDemandDecisionBridge(decision_core=_RejectingDecisionCore())

def _run_demand_bridge_case(payload: Mapping[str, Any]) -> dict[str, Any]:
    request = _Request(
        request_id=str(payload.get("request_id") or "req-snapshot"),
        customer_id=str(payload.get("customer_id") or "cust-snapshot"),
    )
    raw_candidates = payload.get("ranked_candidates") or ()
    ranked = tuple(
        _RoutingCandidate(
            str(item.get("business_id") or ""),
            float(item.get("rank_score") or 0.0),
            blocked=bool(item.get("blocked", False)),
            trace=item.get("trace") or None,
        )
        for item in raw_candidates
    )
    trace = dict(payload.get("trace") or {})
    routing_preparation = {
        "request_id": request.request_id,
        "ranked_candidates": ranked,
        "requires_manual_review": bool(payload.get("requires_manual_review", False)),
        "trace": trace,
    }
    bridge = _build_bridge(payload)
    decision = bridge.evaluate(request=request, routing_preparation=routing_preparation)
    return canonicalize_mapping(
        {
            "request_id": decision.request_id,
            "selected_business_id": decision.selected_business_id,
            "runner_up_business_ids": tuple(decision.runner_up_business_ids),
            "requires_manual_review": decision.requires_manual_review,
            "trace": dict(decision.trace),
        }
    )

def run_project_snapshot_case(case: ProjectSnapshotCase) -> dict[str, Any]:
    if case.scenario_type == "runtime":
        observed = _run_runtime_case(case.payload)
    elif case.scenario_type == "demand_bridge":
        observed = _run_demand_bridge_case(case.payload)
    else:
        raise ValueError(f"Unsupported snapshot scenario_type: {case.scenario_type}")
    contract_diff = compare_contracts(case.expected_contract, observed)
    trace_diff = compare_traces(case.expected_trace, observed.get("trace", {}))
    return {
        "name": case.name,
        "scenario_type": case.scenario_type,
        "observed": observed,
        "contract_diff": contract_diff,
        "trace_diff": trace_diff,
        "ok": contract_diff.equal and trace_diff.equal,
    }

def run_project_snapshot_bundle(root: Path | None = None) -> dict[str, Any]:
    cases = load_project_snapshot_bundle(root)
    results = [run_project_snapshot_case(case) for case in cases]
    return {
        "checked_cases": len(results),
        "failing_cases": [
            {
                "case": result["name"],
                "scenario_type": result["scenario_type"],
                "contract_diff": result["contract_diff"].differing_keys,
                "trace_diff": result["trace_diff"].differing_keys,
            }
            for result in results
            if not result["ok"]
        ],
        "ok": all(result["ok"] for result in results),
    }

__all__ = [
    "ProjectSnapshotCase",
    "load_project_snapshot_bundle",
    "run_project_snapshot_bundle",
    "run_project_snapshot_case",
    "summarize_project_snapshot_bundle",
]
