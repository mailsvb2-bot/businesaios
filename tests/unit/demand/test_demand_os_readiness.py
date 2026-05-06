from __future__ import annotations

from demand_os.demand_os_readiness import evaluate_readiness


class _Capture:
    def capture(self):
        return None


class _Builder:
    def build(self):
        return None


class _Directory:
    def list_profiles(self):
        return ()


class _MatchEngine:
    def build_bundle(self):
        return None


class _Router:
    def prepare(self):
        return None


class _DecisionCore:
    def issue(self):
        return None


class _Dispatcher:
    def dispatch(self):
        return None


def test_demand_os_readiness_requires_real_interfaces() -> None:
    readiness = evaluate_readiness({
        'demand_capture_service': _Capture(),
        'client_intent_builder': _Builder(),
        'business_live_state_builder': _Builder(),
        'business_directory': _Directory(),
        'match_engine': _MatchEngine(),
        'demand_router': _Router(),
        'decision_core': _DecisionCore(),
        'lead_delivery_dispatcher': _Dispatcher(),
    })
    assert readiness.ready is True


def test_demand_os_readiness_rejects_missing_decision_core_even_if_legacy_publisher_exists() -> None:
    readiness = evaluate_readiness({
        'demand_capture_service': _Capture(),
        'client_intent_builder': _Builder(),
        'business_live_state_builder': _Builder(),
        'business_directory': _Directory(),
        'match_engine': _MatchEngine(),
        'demand_router': _Router(),
        'demand_decision_publisher': object(),
        'lead_delivery_dispatcher': _Dispatcher(),
    })
    assert readiness.ready is False
    assert 'decision_core' in readiness.reason


def test_demand_os_readiness_rejects_wrong_component_shapes() -> None:
    readiness = evaluate_readiness({
        'demand_capture_service': object(),
        'client_intent_builder': _Builder(),
        'business_live_state_builder': _Builder(),
        'business_directory': _Directory(),
        'match_engine': _MatchEngine(),
        'demand_router': _Router(),
        'decision_core': _DecisionCore(),
        'lead_delivery_dispatcher': _Dispatcher(),
    })
    assert readiness.ready is False
    assert 'demand_capture_service.capture' in readiness.reason
