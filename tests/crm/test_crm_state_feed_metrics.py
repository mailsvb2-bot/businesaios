from crm.crm_deal_contract import CrmDeal
from crm.state.crm_state_feed import CrmStateFeed
from crm.upsert.crm_upsert_orchestrator import CrmUpsertOrchestrator


def test_state_feed_reports_open_and_won_deals(hubspot_connector, connection):
    orchestrator = CrmUpsertOrchestrator()
    orchestrator.upsert_deal(
        hubspot_connector,
        connection,
        CrmDeal(deal_id='deal-open', title='Open', pipeline_key='default_sales', stage_key='new'),
        idempotency_key='deal-open',
    )
    orchestrator.upsert_deal(
        hubspot_connector,
        connection,
        CrmDeal(deal_id='deal-won', title='Won', pipeline_key='default_sales', stage_key='won'),
        idempotency_key='deal-won',
    )

    snapshot = CrmStateFeed().fetch(hubspot_connector, connection)

    assert snapshot.open_deals == 1
    assert snapshot.won_deals_last_30d == 1
    assert snapshot.metadata['deal_count'] == 2
