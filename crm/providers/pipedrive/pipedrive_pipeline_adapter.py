from __future__ import annotations

from crm.crm_connection_contract import CrmConnectionRef
from crm.crm_pipeline_contract import CrmPipeline
from crm.crm_stage_contract import CrmStage
from crm.providers.common.crm_http_client import CrmHttpRequest
from crm.providers.common.crm_provider_store import CrmProviderStore
from crm.providers.pipedrive.pipedrive_api_config import PipedriveApiConfig
from crm.providers.pipedrive.pipedrive_auth_adapter import PipedriveAuthAdapter


DEFAULT_PIPELINE = CrmPipeline(
    pipeline_key='pipedrive_default',
    display_name='Pipedrive Default',
    stages=(
        CrmStage('new', 'New', 10),
        CrmStage('qualified', 'Qualified', 20),
        CrmStage('won', 'Won', 30, is_closed=True, is_won=True),
        CrmStage('lost', 'Lost', 40, is_closed=True, is_won=False),
    ),
    external_id='pipedrive:pipeline:default',
)


class PipedrivePipelineAdapter:
    def __init__(self, store: CrmProviderStore | None = None, *, auth_adapter: PipedriveAuthAdapter | None = None, api_config: PipedriveApiConfig | None = None) -> None:
        self._store = store
        self._auth_adapter = auth_adapter
        self._api_config = api_config or PipedriveApiConfig()

    def list_pipelines(self, connection: CrmConnectionRef | None = None, *, secret_ref: str | None = None, company_domain: str | None = None) -> tuple[CrmPipeline, ...]:
        if self._auth_adapter is None or not secret_ref or not company_domain:
            assert connection is not None and self._store is not None
            return self._store.list_pipelines(connection)
        client = self._auth_adapter.authorized_client(secret_ref=secret_ref, company_domain=company_domain)
        response = client.send(CrmHttpRequest(method='GET', path='/pipelines'))
        payload = response.json_body if isinstance(response.json_body, dict) else {}
        results = payload.get('data', []) if isinstance(payload.get('data'), list) else []
        return tuple(CrmPipeline(pipeline_key=str(item.get('id') or 'pipeline'), display_name=str(item.get('name') or item.get('id') or 'Pipeline'), stages=tuple(), external_id=str(item.get('id') or '')) for item in results if isinstance(item, dict))

    def upsert(self, connection: CrmConnectionRef, pipeline: CrmPipeline, *, idempotency_key: str, company_domain: str | None = None) -> dict[str, object]:
        if self._auth_adapter is None or not connection.secret_ref or not company_domain:
            assert self._store is not None
            return self._store.upsert_pipeline(connection, pipeline, idempotency_key=idempotency_key)
        client = self._auth_adapter.authorized_client(secret_ref=connection.secret_ref, company_domain=company_domain)
        body = {'name': pipeline.display_name}
        method = 'POST'
        path = '/pipelines'
        if pipeline.external_id:
            method = 'PATCH'
            path = f'/pipelines/{pipeline.external_id}'
        response = client.send(CrmHttpRequest(method=method, path=path, json_body=body))
        payload = response.json_body if isinstance(response.json_body, dict) else {}
        data = payload.get('data') if isinstance(payload.get('data'), dict) else payload
        return {'operation': 'update' if pipeline.external_id else 'create', 'record_id': str(data.get('id') or pipeline.external_id or pipeline.pipeline_key), 'pipeline_key': pipeline.pipeline_key, 'stage_count': len(pipeline.stages), 'idempotency_key': idempotency_key}
