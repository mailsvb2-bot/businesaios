from crm.state.crm_conversion_signal_builder import CrmConversionSignalBuilder
from crm.state.crm_state_snapshot import CrmStateSnapshot


def test_conversion_signal_builder_calculates_rate():
    signal = CrmConversionSignalBuilder().build(CrmStateSnapshot(tenant_id='t', business_id='b', provider_key='hubspot', won_deals_last_30d=2, lost_deals_last_30d=2))
    assert signal['conversion_rate_30d'] == 0.5
