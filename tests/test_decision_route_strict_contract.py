from kernel.decisioning.route_contract import DecisionRouteViolation, extract_strict_route_from_envelope

class _Decision:
    def __init__(self, *, decision_id="d1", correlation_id="c1", issuer_id="businesaios-core", action="pricing_select@v1"):
        self.decision_id = decision_id
        self.correlation_id = correlation_id
        self.issuer_id = issuer_id
        self.action = action

class _Env:
    def __init__(self, decision):
        self.decision = decision

def test_extract_strict_route_ignores_payload_fallbacks():
    route = extract_strict_route_from_envelope(payload={"decision_id": "payload-d", "correlation_id": "payload-c"}, env=_Env(_Decision()))
    assert route.decision_id == "d1"
    assert route.correlation_id == "c1"

def test_extract_strict_route_requires_env_decision_fields():
    try:
        extract_strict_route_from_envelope(payload={"decision_id": "payload-d"}, env=_Env(_Decision(decision_id="")))
    except DecisionRouteViolation as exc:
        assert "decision_id" in str(exc)
    else:
        raise AssertionError("expected strict contract violation")
