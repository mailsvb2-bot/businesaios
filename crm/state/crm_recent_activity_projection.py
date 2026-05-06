from __future__ import annotations

from crm.state.crm_state_snapshot import CrmStateSnapshot


class CrmRecentActivityProjection:
    def project(self, snapshot: CrmStateSnapshot) -> dict[str, object]:
        return {'recent_activity': snapshot.metadata.get('recent_activity', [])}
