from __future__ import annotations

"""Canonical CRM package root.

The package root is the single CRM owner surface. ``crm.public_api`` remains
available only as a compatibility shell for historical imports.
"""

from importlib import import_module

from canon.public_api_alias import install_public_api_alias
from typing import Any

CANON_CRM_PACKAGE_OWNER = True
CANON_CRM_PUBLIC_API = True
CANON_CRM_COMPAT_SHIM = True
CANON_CRM_ROOT_DIRECT_OWNER_EXPORTS = True
CANONICAL_OWNER_CRM_SURFACE = "crm"

_OWNER_MAP = {
    'CrmActivity': ('crm.crm_activity_contract', 'CrmActivity'),
    'CrmConnector': ('crm.crm_connector_contract', 'CrmConnector'),
    'CrmContact': ('crm.crm_contact_contract', 'CrmContact'),
    'CrmDeal': ('crm.crm_deal_contract', 'CrmDeal'),
    'CrmLead': ('crm.crm_lead_contract', 'CrmLead'),
    'CrmPipeline': ('crm.crm_pipeline_contract', 'CrmPipeline'),
    'CrmProvider': ('crm.crm_provider_contract', 'CrmProvider'),
    'CrmStage': ('crm.crm_stage_contract', 'CrmStage'),
    'CrmAppendNoteAction': ('crm.actions.crm_append_note_action', 'CrmAppendNoteAction'),
    'CrmConnectAction': ('crm.actions.crm_connect_action', 'CrmConnectAction'),
    'CrmCreatePipelineAction': ('crm.actions.crm_create_pipeline_action', 'CrmCreatePipelineAction'),
    'CrmUpsertContactAction': ('crm.actions.crm_upsert_contact_action', 'CrmUpsertContactAction'),
    'CrmUpsertDealAction': ('crm.actions.crm_upsert_deal_action', 'CrmUpsertDealAction'),
    'CrmUpsertLeadAction': ('crm.actions.crm_upsert_lead_action', 'CrmUpsertLeadAction'),
    'CrmActionDispatcher': ('crm.execution.crm_action_dispatcher', 'CrmActionDispatcher'),
    'CrmExecutionService': ('crm.execution.crm_execution_service', 'CrmExecutionService'),
    'CrmLeadIdentityResolver': ('crm.leads.crm_lead_identity_resolver', 'CrmLeadIdentityResolver'),
    'CrmLeadIngestionService': ('crm.leads.crm_lead_ingestion_service', 'CrmLeadIngestionService'),
    'RawLeadPayload': ('crm.leads.crm_lead_normalization_contract', 'RawLeadPayload'),
    'CrmLeadNormalizer': ('crm.leads.crm_lead_normalizer', 'CrmLeadNormalizer'),
    'CrmBusinessMemoryAdapter': ('crm.memory.crm_business_memory_adapter', 'CrmBusinessMemoryAdapter'),
    'InMemoryCrmEvidenceStore': ('crm.memory.crm_evidence_store', 'InMemoryCrmEvidenceStore'),
    'CrmMemoryProjection': ('crm.memory.crm_memory_projection', 'CrmMemoryProjection'),
    'CrmConnectionFlow': ('crm.onboarding.crm_connection_flow', 'CrmConnectionFlow'),
    'CrmConnectionResult': ('crm.onboarding.crm_connection_result', 'CrmConnectionResult'),
    'CrmConnectionService': ('crm.onboarding.crm_connection_service', 'CrmConnectionService'),
    'CrmOAuthCallbackHandler': ('crm.onboarding.crm_oauth_callback_handler', 'CrmOAuthCallbackHandler'),
    'CrmPipelineModelBuilder': ('crm.pipeline.crm_pipeline_model_builder', 'CrmPipelineModelBuilder'),
    'CrmPipelineProvisionService': ('crm.pipeline.crm_pipeline_provision_service', 'CrmPipelineProvisionService'),
    'CrmPipelineSyncService': ('crm.pipeline.crm_pipeline_sync_service', 'CrmPipelineSyncService'),
    'CrmPipelineUpsertService': ('crm.pipeline.crm_pipeline_upsert_service', 'CrmPipelineUpsertService'),
    'CrmCapabilityRegistry': ('crm.registry.crm_capability_registry', 'CrmCapabilityRegistry'),
    'CrmConnectorRegistry': ('crm.registry.crm_connector_registry', 'CrmConnectorRegistry'),
    'build_default_provider_catalog': ('crm.registry.crm_provider_catalog', 'build_default_provider_catalog'),
    'CrmProviderRegistry': ('crm.registry.crm_provider_registry', 'CrmProviderRegistry'),
    'CrmProviderSelector': ('crm.registry.crm_provider_selector', 'CrmProviderSelector'),
    'assert_crm_registry_consistency': ('crm.registry.crm_registry_consistency', 'assert_crm_registry_consistency'),
    'CrmStateFeed': ('crm.state.crm_state_feed', 'CrmStateFeed'),
    'CrmStateSnapshot': ('crm.state.crm_state_snapshot', 'CrmStateSnapshot'),
    'CrmStateSynthesizer': ('crm.state.crm_state_synthesizer', 'CrmStateSynthesizer'),
    'CrmWorldStateAdapter': ('crm.state.crm_world_state_adapter', 'CrmWorldStateAdapter'),
    'CrmDedupKeyBuilder': ('crm.upsert.crm_dedup_key_builder', 'CrmDedupKeyBuilder'),
    'CrmDedupMatchPolicy': ('crm.upsert.crm_dedup_match_policy', 'CrmDedupMatchPolicy'),
    'CrmUpsertOrchestrator': ('crm.upsert.crm_upsert_orchestrator', 'CrmUpsertOrchestrator'),
    'CrmUpsertResult': ('crm.upsert.crm_upsert_result', 'CrmUpsertResult'),
    'CrmContactVerifier': ('crm.verification.crm_contact_verifier', 'CrmContactVerifier'),
    'CrmDealVerifier': ('crm.verification.crm_deal_verifier', 'CrmDealVerifier'),
    'CrmWriteVerifier': ('crm.verification.crm_write_verifier', 'CrmWriteVerifier'),
    'CrmWebhookIngestionService': ('crm.webhooks.crm_webhook_ingestion_service', 'CrmWebhookIngestionService'),
}


def _load_attr(module_name: str, attr_name: str) -> Any:
    return getattr(import_module(module_name), attr_name)


def __getattr__(name: str) -> Any:
    if name in {
        'CANON_CRM_PACKAGE_OWNER',
        'CANON_CRM_PUBLIC_API',
        'CANON_CRM_COMPAT_SHIM',
        'CANON_CRM_ROOT_DIRECT_OWNER_EXPORTS',
        'CANONICAL_OWNER_CRM_SURFACE',
    }:
        return globals()[name]
    target = _OWNER_MAP.get(name)
    if target is not None:
        module_name, attr_name = target
        value = _load_attr(module_name, attr_name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))


install_public_api_alias(__name__)

__all__ = [
    'CANON_CRM_PACKAGE_OWNER',
    'CANON_CRM_PUBLIC_API',
    'CANON_CRM_COMPAT_SHIM',
    'CANON_CRM_ROOT_DIRECT_OWNER_EXPORTS',
    'CANONICAL_OWNER_CRM_SURFACE',
    *_OWNER_MAP.keys(),
]
