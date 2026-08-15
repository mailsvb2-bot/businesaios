from __future__ import annotations

from crm.crm_capability_contract import CrmCapabilityDescriptor


def build_bitrix24_capability_descriptor() -> CrmCapabilityDescriptor:
    return CrmCapabilityDescriptor(
        provider_key='bitrix24',
        can_read_contacts=False,
        can_write_contacts=True,
        can_read_deals=False,
        can_write_deals=True,
        can_read_pipelines=True,
        can_write_pipelines=False,
        can_verify_writes=True,
        can_receive_webhooks=False,
        can_oauth_connect=True,
        supports_idempotency=False,
        maturity='live_write_beta',
        metadata={
            'api_surface': 'universal_crm_items',
            'auth_mode': 'oauth_authorization_code_with_refresh',
            'contact_entity_type_id': 3,
            'deal_entity_type_id': 2,
            'write_policy': 'canonical_runtime_only',
            'read_surface': 'pipeline_and_write_verification_only',
            'idempotency': 'provider_does_not_guarantee_request_key_replay',
        },
    )
