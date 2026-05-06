from __future__ import annotations


class CrmPipelineIdentityMap:
    def build(self, *, pipeline_key: str, external_id: str | None) -> dict[str, str]:
        payload = {'pipeline_key': pipeline_key}
        if external_id:
            payload['external_id'] = external_id
        return payload
