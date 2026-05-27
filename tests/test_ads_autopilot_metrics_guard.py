from core.ads.autopilot.campaign_builder import AdsAutopilotCampaignBuilder
from core.ads.autopilot.contract import AdsAutopilotConstraints, AdsAutopilotRequest
from core.ads.autopilot.engine import AdsAutopilotEngine


class _BrokenAds:
    def metrics(self, tenant_id, payload):
        raise RuntimeError('boom')

    def build_plan(self, tenant_id, spec):
        raise AssertionError('must not build when metrics are unavailable')


class _UnsafeAds(_BrokenAds):
    def apply(self, *args, **kwargs):
        return None


class _DummyBuilder:
    def build(self, req):
        return {'channels': req.get('channels') or []}


def _req() -> AdsAutopilotRequest:
    return AdsAutopilotRequest(
        tenant_id='t1',
        objective='profit',
        constraints=AdsAutopilotConstraints(currency='RUB'),
        decision_id='d1',
        correlation_id='c1',
        issuer_id='businesaios-core',
        issued_action='ads_autopilot_tick@v1',
        route='DecisionCore->RuntimeExecutor->AdsAutopilotTick',
    )


def _engine(ads):
    return AdsAutopilotEngine(ads=ads, builder=AdsAutopilotCampaignBuilder(_DummyBuilder()))


def test_ads_autopilot_blocks_when_metrics_are_unavailable():
    out = _engine(_BrokenAds()).tick(_req())
    assert out.status == 'blocked'
    assert out.applied['reason'] == 'metrics_unavailable'


def test_ads_autopilot_rejects_direct_apply_surface():
    try:
        _engine(_UnsafeAds()).tick(_req())
    except ValueError as exc:
        assert 'direct apply surface' in str(exc)
    else:
        raise AssertionError('expected ValueError')
