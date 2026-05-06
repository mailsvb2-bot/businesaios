from __future__ import annotations

from crm.state.crm_state_snapshot import CrmStateSnapshot


class CrmPipelineStateAggregator:
    def aggregate(self, snapshot: CrmStateSnapshot) -> dict[str, object]:
        return {
            'open_deals': snapshot.open_deals,
            'stalled_deals': snapshot.stalled_deals,
            'pipeline_count': snapshot.metadata.get('pipeline_count', 0),
        }
