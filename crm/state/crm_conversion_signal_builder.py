from __future__ import annotations

from crm.state.crm_state_snapshot import CrmStateSnapshot


class CrmConversionSignalBuilder:
    def build(self, snapshot: CrmStateSnapshot) -> dict[str, object]:
        attempts = snapshot.won_deals_last_30d + snapshot.lost_deals_last_30d
        conversion_rate = 0.0 if attempts <= 0 else snapshot.won_deals_last_30d / attempts
        return {'conversion_rate_30d': conversion_rate, 'won_deals_30d': snapshot.won_deals_last_30d}
