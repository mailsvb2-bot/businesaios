from __future__ import annotations


class CrmSignalProjector:
    def project(self, world_state: dict[str, object]) -> dict[str, object]:
        return dict(world_state.get('crm') or {})
