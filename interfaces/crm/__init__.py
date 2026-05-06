"""CRM connector interfaces.

Business-facing CRM support is intentionally collapsed to the single
implemented connector surface. Other named CRM integrations live only in the
registry as explicit not-implemented declarations.
"""

from .hubspot_connector import HubspotConnector
from .registry import CONNECTORS

__all__ = ["HubspotConnector", "CONNECTORS"]
