from __future__ import annotations

from crm.crm_capability_contract import CrmCapabilityDescriptor


def build_salesforce_capability_descriptor() -> CrmCapabilityDescriptor:
    """Describe only the Salesforce surface implemented by this adapter.

    The connector has live contact/deal upserts plus provider read-back used for
    write verification. It does not yet expose canonical contact/deal listing,
    webhook ingestion, or an OAuth authorization-code exchange flow.
    """
    return CrmCapabilityDescriptor(
        provider_key='salesforce',
        can_read_contacts=False,
        can_write_contacts=True,
        can_read_deals=False,
        can_write_deals=True,
        can_read_pipelines=False,
        can_write_pipelines=False,
        can_verify_writes=True,
        can_receive_webhooks=False,
        can_oauth_connect=False,
        supports_idempotency=True,
        maturity='live_write_beta',
        metadata={
            'deal_object': 'Opportunity',
            'api_version': 'v67.0',
            'auth_mode': 'preprovisioned_oauth_token',
            'live_read_surface': 'write_verification_only',
            'planned_event_transport': 'change_data_capture_or_pubsub',
            'write_policy': 'canonical_runtime_only',
        },
    )
