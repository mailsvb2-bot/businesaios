from core.growth.autopilot_engine import AutopilotEngine
from core.growth.autopilot_config import AutopilotRunConfig


class _Sink:
    def emit(self, **kwargs):
        self.last = kwargs


class _BrokenGateway:
    propose = None


def test_autopilot_engine_rejects_noncallable_gateway() -> None:
    engine = AutopilotEngine(
        entitlements_provider=object(),
        ads_service=object(),
        ads_reco_service=object(),
        ads_apply_service=object(),
        trust_score=object(),
        circuit_breaker=object(),
        sink=_Sink(),
        cfg=AutopilotRunConfig(),
        proposal_gateway=_BrokenGateway(),
    )
    try:
        engine._ensure_guarded_execution_contract()
    except RuntimeError as exc:
        assert 'proposal_gateway' in str(exc)
    else:
        raise AssertionError('expected RuntimeError')
