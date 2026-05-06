from __future__ import annotations

from crm.crm_pipeline_contract import CrmPipeline
from crm.pipeline.crm_pipeline_verifier import CrmPipelineVerifier


class CrmPipelineUpsertService:
    def __init__(self, verifier: CrmPipelineVerifier | None = None) -> None:
        self._verifier = verifier or CrmPipelineVerifier()

    def upsert(self, *, provision_result: dict[str, object], pipeline: CrmPipeline) -> dict[str, object]:
        verified = self._verifier.verify_expected_shape(pipeline)
        return {'upserted': True, 'verified': verified, 'pipeline_key': pipeline.pipeline_key, 'provision_result': provision_result}
