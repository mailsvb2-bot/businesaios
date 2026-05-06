from crm.crm_capability_contract import CrmCapabilityDescriptor


def build_pipedrive_capability_descriptor() -> CrmCapabilityDescriptor:
    return CrmCapabilityDescriptor(
        provider_key='pipedrive',
        can_read_contacts=True,
        can_write_contacts=True,
        can_read_deals=True,
        can_write_deals=True,
        can_read_pipelines=True,
        can_write_pipelines=False,
        can_verify_writes=True,
        can_receive_webhooks=True,
        can_oauth_connect=True,
        supports_idempotency=True,
        maturity='real',
    )
