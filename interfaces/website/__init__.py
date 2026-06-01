"""Website connector interfaces.

The implemented website integration surface is intentionally collapsed to
SiteConnector. Other connector names live only in the registry as explicit
not-implemented declarations.
"""

from .registry import CONNECTORS
from .site_connector import SiteConnector

__all__ = ["SiteConnector", "CONNECTORS"]
