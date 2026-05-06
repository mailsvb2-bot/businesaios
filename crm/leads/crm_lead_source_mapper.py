from __future__ import annotations

from crm.crm_source_contract import CrmSource


class CrmLeadSourceMapper:
    def map(self, raw_source: str | None) -> CrmSource:
        source_key = (raw_source or 'unknown').strip().lower().replace(' ', '_')
        return CrmSource(source_key=source_key, display_name=source_key.replace('_', ' ').title(), channel=source_key)
