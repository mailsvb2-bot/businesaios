from __future__ import annotations

import pytest

from crm.crm_connection_contract import CrmConnectionRef
from crm.crm_contact_contract import CrmContact
from crm.crm_deal_contract import CrmDeal
from crm.crm_identity_contract import CrmIdentity
from crm.crm_lead_contract import CrmLead
from crm.crm_source_contract import CrmSource
from crm.providers.hubspot.hubspot_connector import HubSpotConnector


@pytest.fixture()
def hubspot_connector() -> HubSpotConnector:
    return HubSpotConnector()


@pytest.fixture()
def connection() -> CrmConnectionRef:
    return CrmConnectionRef(tenant_id='tenant-1', business_id='biz-1', provider_key='hubspot', connection_id='hubspot:tenant-1:biz-1', status='active', secret_ref='secret://crm/hubspot')


@pytest.fixture()
def sample_lead() -> CrmLead:
    return CrmLead(lead_id='lead-1', tenant_id='tenant-1', business_id='biz-1', full_name='Ada Lovelace', email='ada@example.com', company_name='Analytical Engines', source=CrmSource('website', 'Website', 'website'), identity=CrmIdentity(canonical_key='ada@example.com', email='ada@example.com'))


@pytest.fixture()
def sample_contact() -> CrmContact:
    return CrmContact(contact_id='contact-1', full_name='Ada Lovelace', identity=CrmIdentity(canonical_key='ada@example.com', email='ada@example.com'))


@pytest.fixture()
def sample_deal() -> CrmDeal:
    return CrmDeal(deal_id='deal-1', title='Pilot Deal', pipeline_key='default_sales', stage_key='new')
