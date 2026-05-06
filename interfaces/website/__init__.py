"""Website connector interfaces.

The implemented website integration surface is intentionally collapsed to
SiteConnector. Other connector names live only in the registry as explicit
not-implemented declarations.
"""

from .site_connector import SiteConnector
from .registry import CONNECTORS

__all__ = ["SiteConnector", "CONNECTORS"]
