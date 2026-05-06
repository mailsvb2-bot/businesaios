from __future__ import annotations

from crm.crm_connection_contract import CrmConnectionRef
from crm.crm_pipeline_contract import CrmPipeline
from crm.crm_stage_contract import CrmStage
from crm.providers.common.crm_http_client import CrmHttpRequest
from crm.providers.common.crm_provider_store import CrmProviderStore
from crm.providers.hubspot.hubspot_api_config import HubSpotApiConfig
from crm.providers.hubspot.hubspot_auth_adapter import HubSpotAuthAdapter


DEFAULT_PIPELINE = CrmPipeline(
    pipeline_key='hubspot_default',
    display_name='HubSpot Default',
    stages=(
        CrmStage('new', 'New', 10),
        CrmStage('qualified', 'Qualified', 20),
        CrmStage('won', 'Won', 30, is_closed=True, is_won=True),
        CrmStage('lost', 'Lost', 40, is_closed=True, is_won=False),
    ),
    external_id='hubspot:pipeline:default',
)


class HubSpotPipelineAdapter:
    def __init__(self, store: CrmProviderStore | None = None, *, auth_adapter: HubSpotAuthAdapter | None = None, api_config: HubSpotApiConfig | None = None) -> None:
        self._store = store
        self._auth_adapter = auth_adapter
        self._api_config = api_config or HubSpotApiConfig()

    def list_pipelines(self, connection: CrmConnectionRef | None = None, *, secret_ref: str | None = None) -> tuple[CrmPipeline, ...]:
        if self._auth_adapter is None or not secret_ref:
            assert connection is not None and self._store is not None
            return self._store.list_pipelines(connection)
        client = self._auth_adapter.authorized_client(secret_ref=secret_ref)
        response = client.send(CrmHttpRequest(method='GET', path='/crm/v3/pipelines/deals'))
        payload = response.json_body if isinstance(response.json_body, dict) else {}
        out=[]
        for item in payload.get('results', []):
            if not isinstance(item, dict):
                continue
            stages=[]
            for idx, stage in enumerate(item.get('stages', []), start=1):
                if not isinstance(stage, dict):
                    continue
                metadata = stage.get('metadata') if isinstance(stage.get('metadata'), dict) else {}
                stages.append(CrmStage(str(stage.get('id') or f'stage-{idx}'), str(stage.get('label') or stage.get('id') or f'Stage {idx}'), idx * 10, is_closed=bool(metadata.get('isClosed')), is_won=bool(metadata.get('probability') == '1.0')))
            out.append(CrmPipeline(pipeline_key=str(item.get('id') or item.get('label') or 'pipeline'), display_name=str(item.get('label') or item.get('id') or 'Pipeline'), stages=tuple(stages), external_id=str(item.get('id') or '')))
        return tuple(out)

    def upsert(self, connection: CrmConnectionRef, pipeline: CrmPipeline, *, idempotency_key: str) -> dict[str, object]:
        if self._auth_adapter is None or not connection.secret_ref:
            assert self._store is not None
            return self._store.upsert_pipeline(connection, pipeline, idempotency_key=idempotency_key)
        client = self._auth_adapter.authorized_client(secret_ref=connection.secret_ref)
        body = {'label': pipeline.display_name, 'displayOrder': 0, 'stages': [{'label': s.display_name, 'displayOrder': s.sort_order, 'metadata': {'isClosed': s.is_closed, 'probability': '1.0' if s.is_won else '0.0'}} for s in pipeline.stages]}
        path = '/crm/v3/pipelines/deals'
        method = 'POST'
        if pipeline.external_id:
            path = f'/crm/v3/pipelines/deals/{pipeline.external_id}'
            method = 'PATCH'
        response = client.send(CrmHttpRequest(method=method, path=path, json_body=body))
        payload = response.json_body if isinstance(response.json_body, dict) else {}
        return {'operation': 'update' if pipeline.external_id else 'create', 'record_id': str(payload.get('id') or pipeline.external_id or pipeline.pipeline_key), 'pipeline_key': pipeline.pipeline_key, 'stage_count': len(pipeline.stages), 'idempotency_key': idempotency_key}
