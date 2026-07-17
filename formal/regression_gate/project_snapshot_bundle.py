from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping

from config.execution_contract import (
    CANONICAL_DECISION_PATH,
    CANONICAL_OPTIMIZATION_TARGET,
)
from core.actions.names import ACTION_ROUTE_LEAD_V1
from core.ai import (
    _reset_decision_core_singleton_for_tests,
    set_decision_core_singleton,
)
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


class _SnapshotEnvelopeCore:
    """Test-only envelope fixture preserving historical snapshot choices.

    It does not expose decide/optimize aliases and is registered as the exact
    process singleton for the bounded snapshot call. Production routing uses the
    real DemandRoutePolicyV1 through core.ai.DecisionCore.
    """

    CANON_NON_RUNTIME_REGRESSION_FIXTURE = True

    def __init__(
        self,
        *,
        mode: str,
        selected_business_id: str,
    ) -> None:
        self._mode = str(mode or "reject")
        self._selected_business_id = str(selected_business_id or "").strip()

    def issue(self, state: Any) -> SimpleNamespace:
        route = dict(getattr(state, "meta", {}).get("demand_route") or {})
        candidates = [
            dict(item)
            for item in route.get("candidates") or ()
            if isinstance(item, dict)
        ]
        selected = None
        if self._mode == "select":
            selected = next(
                (
                    candidate
                    for candidate in candidates
                    if str(candidate.get("business_id") or "").strip()
                    == self._selected_business_id
                ),
                None,
            )

        payload: dict[str, Any] = {
            "request_id": str(route.get("request_id") or ""),
            "requires_manual_review": selected is None,
            "candidate_count": len(candidates),
            "blocked_candidate_count": int(
                route.get("blocked_candidate_count") or 0
            ),
            "runner_up_business_ids": [],
            "rejections": [],
        }
        decision_id = "snapshot-reject"
        if selected is None:
            # Preserve the historical public snapshot exactly. The former fake
            # selector returned no candidate, and the bridge exposed this reason.
            payload["manual_review_reason"] = (
                "decision_core_rejected_all_candidates"
            )
        else:
            selected_business_id = str(
                selected.get("business_id") or ""
            ).strip()
            payload.update(
                {
                    "selected_business_id": selected_business_id,
                    "delivery_channel": str(
                        selected.get("channel") or ""
                    ),
                    "selected_candidate_id": str(
                        selected.get("candidate_id") or ""
                    ),
                    "selection_score": float(
                        selected.get("score") or 0.0
                    ),
                    "runner_up_business_ids": [
                        str(candidate.get("business_id") or "").strip()
                        for candidate in candidates
                        if str(
                            candidate.get("business_id") or ""
                        ).strip()
                        and str(
                            candidate.get("business_id") or ""
                        ).strip()
                        != selected_business_id
                    ],
                }
            )
            decision_id = "snapshot-allow"

        return SimpleNamespace(
            decision=SimpleNamespace(
                action=ACTION_ROUTE_LEAD_V1,
                payload=payload,
                decision_id=decision_id,
                correlation_id=str(route.get("request_id") or decision_id),
            )
        )


class _RoutingCandidate:
    def __init__(
        self,
        business_id: str,
        rank_score: float,
        *,
        blocked: bool = False,
        trace: Mapping[str, Any] | None = None,
    ) -> None:
        self.business_id = business_id
        self.rank_score = rank_score
        self.blocked = blocked
        self.trace = dict(
            trace
            or {
                "adjusted_score": rank_score,
                "match_score": rank_score,
            }
        )


class _Request:
    def __init__(
        self,
        request_id: str,
        customer_id: str = "cust-snapshot",
    ) -> None:
        self.request_id = request_id
        self.customer_id = customer_id


def _bundle_root() -> Path:
    return (
        Path(__file__).resolve().parent
        / "fixtures"
        / "project_snapshot_bundle"
    )


def load_project_snapshot_bundle(
    root: Path | None = None,
) -> list[ProjectSnapshotCase]:
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


def summarize_project_snapshot_bundle(
    root: Path | None = None,
) -> dict[str, Any]:
    cases = load_project_snapshot_bundle(root)
    return {
        "count": len(cases),
        "names": tuple(case.name for case in cases),
        "scenario_types": tuple(
            sorted({case.scenario_type for case in cases})
        ),
        "ok": bool(cases),
    }


def _run_runtime_case(payload: Mapping[str, Any]) -> dict[str, Any]:
    return dict(replay_runtime_decision(payload))


def _build_snapshot_core(
    scenario: Mapping[str, Any],
) -> _SnapshotEnvelopeCore:
    return _SnapshotEnvelopeCore(
        mode=str(scenario.get("mode") or "reject"),
        selected_business_id=str(
            scenario.get("selected_business_id") or ""
        ),
    )


def _run_demand_bridge_case(payload: Mapping[str, Any]) -> dict[str, Any]:
    request = _Request(
        request_id=str(payload.get("request_id") or "req-snapshot"),
        customer_id=str(
            payload.get("customer_id") or "cust-snapshot"
        ),
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
        "requires_manual_review": bool(
            payload.get("requires_manual_review", False)
        ),
        "trace": trace,
    }

    _reset_decision_core_singleton_for_tests()
    core = _build_snapshot_core(payload)
    set_decision_core_singleton(core)
    try:
        bridge = CanonicalDemandDecisionBridge(decision_core=core)
        decision = bridge.evaluate(
            request=request,
            routing_preparation=routing_preparation,
        )
    finally:
        _reset_decision_core_singleton_for_tests()

    return canonicalize_mapping(
        {
            "request_id": decision.request_id,
            "selected_business_id": decision.selected_business_id,
            "runner_up_business_ids": tuple(
                decision.runner_up_business_ids
            ),
            "requires_manual_review": decision.requires_manual_review,
            "trace": dict(decision.trace),
        }
    )


def run_project_snapshot_case(
    case: ProjectSnapshotCase,
) -> dict[str, Any]:
    if case.scenario_type == "runtime":
        observed = _run_runtime_case(case.payload)
    elif case.scenario_type == "demand_bridge":
        observed = _run_demand_bridge_case(case.payload)
    else:
        raise ValueError(
            f"Unsupported snapshot scenario_type: {case.scenario_type}"
        )
    contract_diff = compare_contracts(case.expected_contract, observed)
    trace_diff = compare_traces(
        case.expected_trace,
        observed.get("trace", {}),
    )
    return {
        "name": case.name,
        "scenario_type": case.scenario_type,
        "observed": observed,
        "contract_diff": contract_diff,
        "trace_diff": trace_diff,
        "ok": contract_diff.equal and trace_diff.equal,
    }


def run_project_snapshot_bundle(
    root: Path | None = None,
) -> dict[str, Any]:
    cases = load_project_snapshot_bundle(root)
    results = [run_project_snapshot_case(case) for case in cases]
    return {
        "checked_cases": len(results),
        "failing_cases": [
            {
                "case": result["name"],
                "scenario_type": result["scenario_type"],
                "contract_diff": result[
                    "contract_diff"
                ].differing_keys,
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
