from __future__ import annotations

from pathlib import Path

from crm import public_api

REPO_ROOT = Path(__file__).resolve().parents[2]
CRM_PACKAGE_ROOT = REPO_ROOT / 'crm'

EXPECTED_EXPORTS = {
    'actions': {'CrmAppendNoteAction', 'CrmConnectAction', 'CrmCreatePipelineAction', 'CrmUpsertContactAction', 'CrmUpsertDealAction', 'CrmUpsertLeadAction'},
    'execution': {'CrmActionDispatcher', 'CrmExecutionService'},
    'leads': {'CrmLeadIdentityResolver', 'CrmLeadIngestionService', 'CrmLeadNormalizer', 'RawLeadPayload'},
    'memory': {'CrmBusinessMemoryAdapter', 'CrmMemoryProjection', 'InMemoryCrmEvidenceStore'},
    'onboarding': {'CrmConnectionFlow', 'CrmConnectionResult', 'CrmConnectionService', 'CrmOAuthCallbackHandler'},
    'pipeline': {'CrmPipelineModelBuilder', 'CrmPipelineProvisionService', 'CrmPipelineSyncService', 'CrmPipelineUpsertService'},
    'registry': {'CrmCapabilityRegistry', 'CrmConnectorRegistry', 'CrmProviderRegistry', 'CrmProviderSelector', 'assert_crm_registry_consistency', 'build_default_provider_catalog'},
    'state': {'CrmStateFeed', 'CrmStateSnapshot', 'CrmStateSynthesizer', 'CrmWorldStateAdapter'},
    'upsert': {'CrmDedupKeyBuilder', 'CrmDedupMatchPolicy', 'CrmUpsertOrchestrator', 'CrmUpsertResult'},
    'verification': {'CrmContactVerifier', 'CrmDealVerifier', 'CrmWriteVerifier'},
    'webhooks': {'CrmWebhookIngestionService'},
}


def test_crm_packages_import_direct_owners_without_local_public_api_wrapper_hop() -> None:
    for package_name, expected_names in EXPECTED_EXPORTS.items():
        init_path = CRM_PACKAGE_ROOT / package_name / '__init__.py'
        contents = init_path.read_text(encoding='utf-8')
        assert '_public_api' not in contents, f'{package_name} must not hop through local *_public_api wrappers'
        for expected_name in expected_names:
            assert expected_name in contents


def test_crm_public_api_exposes_all_expected_exports() -> None:
    visible = set(public_api.__all__)
    assert 'CANON_CRM_PUBLIC_API' in visible
    for expected_names in EXPECTED_EXPORTS.values():
        assert expected_names <= visible
