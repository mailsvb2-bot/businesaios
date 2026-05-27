from core.growth.autopilot_config import AutopilotRunConfig
from core.growth.autopilot_engine import AutopilotEngine


class _Ent:
    class _Mode:
        value = 'autopilot'
    def get_ads_entitlements(self, tenant_id):
        return type('Ent', (), {'mode': self._Mode()})()


class _Trust:
    def allow_autopilot(self, **kwargs):
        return True


class _Breaker:
    def is_tripped(self, **kwargs):
        return False


class _Sink:
    def emit(self, **kwargs):
        self.last = kwargs


class _Ads:
    async def import_stats(self, **kwargs):
        return 0


class _Reco:
    def propose_and_cache(self, **kwargs):
        return []


class _Gateway:
    def propose(self, **kwargs):
        return 'p1'


def test_growth_autopilot_rejects_non_canonical_issuer():
    engine = AutopilotEngine(
        entitlements_provider=_Ent(),
        ads_service=_Ads(),
        ads_reco_service=_Reco(),
        ads_apply_service=None,
        trust_score=_Trust(),
        circuit_breaker=_Breaker(),
        sink=_Sink(),
        cfg=AutopilotRunConfig(),
        proposal_gateway=_Gateway(),
    )
    import asyncio
    out = asyncio.run(engine.run(
        tenant_id='t1', platform='meta', account_id='a1', decision_id='d1', correlation_id='c1', issuer_id='foreign-core'
    ))
    assert out.ok is False
    assert 'issuer_id must be' in out.message
