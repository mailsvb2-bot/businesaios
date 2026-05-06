from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

EXPECTED_ISSUER_ID = "businesaios-core"
CANONICAL_ROUTE = "DecisionCore->RuntimeExecutor"


class DecisionRouteViolation(ValueError):
    pass


@dataclass(frozen=True)
class DecisionRoute:
    decision_id: str
    correlation_id: str
    issuer_id: str
    action: str
    route: str

    def validate(self, *, expected_action: str | None = None) -> None:
        if not str(self.decision_id or "").strip():
            raise DecisionRouteViolation("decision_id is required")
        if not str(self.correlation_id or "").strip():
            raise DecisionRouteViolation("correlation_id is required")
        if not str(self.issuer_id or "").strip():
            raise DecisionRouteViolation("issuer_id is required")
        if self.issuer_id != EXPECTED_ISSUER_ID:
            raise DecisionRouteViolation(f"issuer_id must be {EXPECTED_ISSUER_ID!r}, got {self.issuer_id!r}")
        if not str(self.action or "").strip():
            raise DecisionRouteViolation("action is required")
        if expected_action is not None and self.action != expected_action:
            raise DecisionRouteViolation(f"action must be {expected_action!r}, got {self.action!r}")
        route = str(self.route or "").strip()
        if not route:
            raise DecisionRouteViolation("route is required")
        if not route.startswith(CANONICAL_ROUTE):
            raise DecisionRouteViolation(
                f"route must start with canonical executor path {CANONICAL_ROUTE!r}, got {route!r}"
            )


def canonical_runtime_route(*segments: str) -> str:
    suffix: list[str] = []
    for segment in segments:
        part = str(segment or "").strip().strip("-").strip(">")
        if not part:
            continue
        if part in {"DecisionCore", "RuntimeExecutor"}:
            continue
        suffix.append(part)
    if not suffix:
        return CANONICAL_ROUTE
    return CANONICAL_ROUTE + "->" + "->".join(suffix)


def _require_decision(env: Any) -> Any:
    if env is None or not hasattr(env, "decision"):
        raise DecisionRouteViolation("DecisionCore-issued envelope is required")
    return env.decision


def extract_route_from_envelope(*, payload: Dict[str, Any], env: Any) -> DecisionRoute:
    p = payload or {}
    d = _require_decision(env)
    return DecisionRoute(
        decision_id=str(getattr(d, "decision_id", "") or p.get("decision_id") or "").strip(),
        correlation_id=str(getattr(d, "correlation_id", "") or p.get("correlation_id") or "").strip(),
        issuer_id=str(getattr(d, "issuer_id", "") or p.get("issuer_id") or "").strip(),
        action=str(getattr(d, "action", "") or "").strip(),
        route=canonical_runtime_route(),
    )


def extract_strict_route_from_envelope(*, payload: Dict[str, Any], env: Any) -> DecisionRoute:
    _ = payload or {}
    route = extract_route_from_envelope(payload={}, env=env)
    route.validate()
    return route
