from __future__ import annotations

from crm.crm_state_contract import CrmStateSlice
from crm.state.crm_conversion_signal_builder import CrmConversionSignalBuilder
from crm.state.crm_funnel_health_signal import CrmFunnelHealthSignal
from crm.state.crm_state_snapshot import CrmStateSnapshot


class CrmStateSynthesizer:
    def __init__(self) -> None:
        self._health_builder = CrmFunnelHealthSignal()
        self._conversion_builder = CrmConversionSignalBuilder()

    def synthesize(self, snapshot: CrmStateSnapshot) -> CrmStateSlice:
        return CrmStateSlice(
            tenant_id=snapshot.tenant_id,
            business_id=snapshot.business_id,
            provider_key=snapshot.provider_key,
            funnel_health=self._health_builder.build(snapshot),
            open_deals=snapshot.open_deals,
            stale_deals=snapshot.stalled_deals,
            recent_conversions=snapshot.won_deals_last_30d,
            metadata=self._conversion_builder.build(snapshot),
        )
