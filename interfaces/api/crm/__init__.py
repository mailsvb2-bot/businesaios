from __future__ import annotations

class CrmAdminApi:
    route_prefix = '/api/crm/admin'

class CrmConnectionApi:
    route_prefix = '/api/crm/connection'

class CrmLeadApi:
    route_prefix = '/api/crm/lead'

class CrmPipelineApi:
    route_prefix = '/api/crm/pipeline'

class CrmWebhookApi:
    route_prefix = '/api/crm/webhook'

__all__ = [
    'CrmAdminApi','CrmConnectionApi','CrmLeadApi','CrmPipelineApi','CrmWebhookApi',
]
_MODULE_EXPORTS = {
    'crm_admin_api': {'CrmAdminApi': f'{__name__}:CrmAdminApi'},
    'crm_connection_api': {'CrmConnectionApi': f'{__name__}:CrmConnectionApi'},
    'crm_lead_api': {'CrmLeadApi': f'{__name__}:CrmLeadApi'},
    'crm_pipeline_api': {'CrmPipelineApi': f'{__name__}:CrmPipelineApi'},
    'crm_webhook_api': {'CrmWebhookApi': f'{__name__}:CrmWebhookApi'},
}
