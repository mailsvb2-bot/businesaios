from __future__ import annotations

from crm.state.crm_state_snapshot import CrmStateSnapshot


class CrmFunnelHealthSignal:
    def build(self, snapshot: CrmStateSnapshot) -> str:
        if snapshot.stalled_deals > max(3, snapshot.won_deals_last_30d):
            return 'attention_required'
        if snapshot.won_deals_last_30d > 0:
            return 'healthy'
        return 'unknown'
