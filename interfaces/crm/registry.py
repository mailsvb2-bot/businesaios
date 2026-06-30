"""Honest CRM connector registry.

The legacy interfaces registry remains intentionally conservative. It exposes
HubSpot as the only implemented named CRM surface while keeping all other CRM
names as explicit not-implemented declarations. That avoids a shadow catalog
and keeps the public matrix honest.
"""

from __future__ import annotations


from interfaces.common.registry_capability_contract import build_registry_entry

CONNECTORS = {
    'hubspot': build_registry_entry(
        name='hubspot',
        status='implemented',
        read=True,
        write=True,
        verify=True,
        supports_dry_run=False,
        supports_idempotency=True,
        production_ready=False,
        action_types=(),
    ),
    'amo': build_registry_entry(name='amo', status='not_implemented'),
    'bitrix': build_registry_entry(name='bitrix', status='not_implemented'),
    'generic_crm': build_registry_entry(name='generic_crm', status='not_implemented'),
    'pipedrive': build_registry_entry(name='pipedrive', status='not_implemented'),
    'salesforce': build_registry_entry(name='salesforce', status='not_implemented'),
}

__all__ = ['CONNECTORS']
