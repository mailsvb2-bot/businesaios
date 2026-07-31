from __future__ import annotations
import copy, hashlib, json, time
from typing import Any
from application.decision_policy.policy_stage import propose_action
from core.events.event_types import SHADOW_DECISION_EVALUATED, SHADOW_OUTCOME_ATTRIBUTED, SHADOW_PRODUCTION_OUTCOME_OBSERVED
CANON_SHADOW_EVIDENCE_ONLY = True
class _Trace:
    def try_add_step(self, **_kwargs: Any) -> None: pass
def _float(value: Any) -> float:
    try: return float(value or 0.0)
    except (TypeError, ValueError): return 0.0
def _data(event: Any) -> dict[str, Any]: return event if isinstance(event, dict) else vars(event)
def _payload(event: Any) -> dict[str, Any]: return dict(_data(event).get("payload") or {})
def _digest(value: Any) -> str: return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()

class ShadowDecisionLedger:
    """Evidence-only ledger. It never selects, signs, executes, or deploys decisions."""
    def __init__(self, event_log: Any) -> None: self.event_log = event_log
    def _events(self, decision_id: str, event_type: str) -> list[Any]:
        try: return list(self.event_log.get_events(str(decision_id), event_type))
        except Exception: return []
    def record(self, envelope: Any, row: dict[str, Any]) -> dict[str, Any]:
        decision = envelope.decision; row = {"tenant_id": str(getattr(self.event_log, "tenant_id", "")), **row}
        self.event_log.emit(event_type=SHADOW_DECISION_EVALUATED, source="shadow_mode", user_id=str(decision.payload.get("actor_id") or "shadow"), decision_id=str(decision.decision_id), correlation_id=str(decision.correlation_id), payload=row)
        return row
    def record_production_outcome(self, decision_id: str, actual_reward: float):
        existing = self._events(decision_id, SHADOW_PRODUCTION_OUTCOME_OBSERVED)
        if existing: return _payload(existing[-1])
        decisions = self._events(decision_id, SHADOW_DECISION_EVALUATED)
        if not decisions: return None
        observed = _payload(decisions[-1]); row = {"candidate_policy_id": observed.get("candidate_policy_id"), "production_action": observed.get("production_action"), "candidate_action": observed.get("candidate_action"), "actual_reward": float(actual_reward), "counterfactual": False, "external_effect": False}
        self.event_log.emit(event_type=SHADOW_PRODUCTION_OUTCOME_OBSERVED, source="shadow_mode", user_id="shadow", decision_id=str(decision_id), correlation_id=None, payload=row)
        return row
    def attribute_counterfactual(self, decision_id: str, candidate_reward: float, *, evaluator_id: str, evidence_ref: str):
        existing = self._events(decision_id, SHADOW_OUTCOME_ATTRIBUTED)
        if existing: return _payload(existing[-1])
        production, decisions = self._events(decision_id, SHADOW_PRODUCTION_OUTCOME_OBSERVED), self._events(decision_id, SHADOW_DECISION_EVALUATED)
        if not production or not decisions or not str(evaluator_id).strip() or not str(evidence_ref).strip(): return None
        observed, actual = _payload(decisions[-1]), _float(_payload(production[-1]).get("actual_reward"))
        row = {"candidate_policy_id": observed.get("candidate_policy_id"), "production_action": observed.get("production_action"), "candidate_action": observed.get("candidate_action"), "actual_reward": actual, "candidate_reward": float(candidate_reward), "regret": max(0.0, float(candidate_reward) - actual), "counterfactual": True, "evaluator_id": str(evaluator_id), "evidence_ref": str(evidence_ref), "external_effect": False}
        self.event_log.emit(event_type=SHADOW_OUTCOME_ATTRIBUTED, source="shadow_mode", user_id="shadow", decision_id=str(decision_id), correlation_id=None, payload=row)
        return row
    def metrics(self, candidate_policy_id: str | None = None) -> dict[str, float | int]:
        decisions, production, outcomes = [], [], []
        try: events = self.event_log.iter_events()
        except Exception: events = ()
        for event in events:
            kind = _data(event).get("event_type"); row = _payload(event)
            if candidate_policy_id and row.get("candidate_policy_id") != candidate_policy_id: continue
            if kind == SHADOW_DECISION_EVALUATED: decisions.append(row)
            elif kind == SHADOW_PRODUCTION_OUTCOME_OBSERVED: production.append(row)
            elif kind == SHADOW_OUTCOME_ATTRIBUTED and row.get("counterfactual") is True: outcomes.append(row)
        total = len(decisions); latencies = sorted(_float(row.get("latency_ms")) for row in decisions)
        avg = lambda key, rows: sum(_float(row.get(key)) for row in rows) / len(rows) if rows else 0.0
        return {"decision_count": total, "production_outcome_count": len(production), "outcome_count": len(outcomes), "error_rate": sum(row.get("status") != "evaluated" for row in decisions) / total if total else 1.0, "disagreement_rate": sum(row.get("candidate_action") != row.get("production_action") for row in decisions) / total if total else 1.0, "critical_violations": sum(bool(row.get("schema_error") or row.get("error")) for row in decisions), "p95_latency_ms": latencies[int((len(latencies) - 1) * 0.95)] if latencies else 0.0, "average_cost_increase": avg("cost_increase", decisions), "average_regret": avg("regret", outcomes)}

class ShadowEvaluator:
    """Runs a configured candidate beside DecisionCore and records evidence only."""
    def __init__(self, ledger: ShadowDecisionLedger | None = None, schemas: Any = None) -> None: self.ledger, self.schemas = ledger, schemas
    def evaluate(self, dataset: Any, policy: Any) -> float:
        fn = policy if callable(policy) else next((getattr(policy, name, None) for name in ("predict", "act", "select") if callable(getattr(policy, name, None))), None)
        if fn is None: return 1.0
        errors = total = 0
        for state, expected in dataset: errors += fn(state) != expected; total += 1
        return errors / total if total else 1.0
    def observe(self, state: Any, production_envelope: Any, candidate_policy: Any):
        if candidate_policy is None or self.ledger is None: return None
        decision, started = production_envelope.decision, time.perf_counter_ns()
        row = {"status": "evaluated", "production_policy_id": str(decision.policy_id), "candidate_policy_id": str(getattr(candidate_policy, "id", "")), "production_action": str(decision.action), "state_hash": _digest(state), "production_payload_hash": _digest(decision.payload), "production_cost": _float(decision.payload.get("expected_cost")), "simulation": True, "observe_only": True, "writes_outbox": False, "external_effect": False, "decision_authority": "DecisionCore"}
        try:
            candidate = propose_action(policy=candidate_policy, state=copy.deepcopy(state), trace=_Trace())
            payload, action = dict(getattr(candidate, "payload", {}) or {}), str(getattr(candidate, "action", ""))
            row.update(candidate_action=action, candidate_payload_hash=_digest(payload), candidate_expected_reward=_float(payload.get("expected_reward")), candidate_cost=_float(payload.get("expected_cost")), candidate_risk=_float(payload.get("risk_score")))
            row["cost_increase"] = max(0.0, row["candidate_cost"] - row["production_cost"])
            if self.schemas is not None:
                try: self.schemas.validate(action, payload)
                except Exception as exc: row.update(status="invalid", schema_error=exc.__class__.__name__)
        except Exception as exc: row.update(status="failed", error=exc.__class__.__name__, candidate_action="", cost_increase=0.0)
        row["latency_ms"] = (time.perf_counter_ns() - started) / 1_000_000
        try: return self.ledger.record(production_envelope, row)
        except Exception: return row
    def record_production_outcome(self, decision_id: str, actual_reward: float): return None if self.ledger is None else self.ledger.record_production_outcome(decision_id, actual_reward)
    def attribute_counterfactual(self, decision_id: str, candidate_reward: float, *, evaluator_id: str, evidence_ref: str): return None if self.ledger is None else self.ledger.attribute_counterfactual(decision_id, candidate_reward, evaluator_id=evaluator_id, evidence_ref=evidence_ref)
    def metrics(self, candidate_policy_id: str | None = None): return {} if self.ledger is None else self.ledger.metrics(candidate_policy_id)
    def run(self, policy: Any, _live_stream: Any): return self.metrics(str(getattr(policy, "id", "")) or None)
