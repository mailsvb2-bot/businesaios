from execution.market_intelligence_advanced_models import HumanFeedbackEvent, TrendPoint
from execution.market_intelligence_human_feedback import HumanFeedbackLoop, HumanFeedbackStore
from execution.market_intelligence_trend_engine import FileTrendStore, TemporalTrendEngine


def test_trend_engine_computes_positive_slope(tmp_path):
    engine = TemporalTrendEngine(store=FileTrendStore(root_dir=tmp_path / 'trends'))
    engine.observe(TrendPoint(tenant_id='t1', entity_id='crm', metric='demand', value=10))
    engine.observe(TrendPoint(tenant_id='t1', entity_id='crm', metric='demand', value=20))
    summary = engine.summarize(tenant_id='t1', entity_id='crm', metric='demand')
    assert summary.slope > 0


def test_human_feedback_summary(tmp_path):
    loop = HumanFeedbackLoop(store=HumanFeedbackStore(root_dir=tmp_path / 'feedback'))
    loop.record(HumanFeedbackEvent(tenant_id='t1', entity_id='crm', label='validated', score_delta=0.3, tags=('important',)))
    loop.record(HumanFeedbackEvent(tenant_id='t1', entity_id='crm', label='false_positive', is_false_positive=True, score_delta=-0.2))
    summary = loop.summarize(tenant_id='t1', entity_id='crm')
    assert summary['events_count'] == 2
    assert summary['false_positives'] == 1
