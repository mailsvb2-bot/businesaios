from __future__ import annotations

from dataclasses import dataclass, field

from execution.effectors.base import ConnectorEffectorBase
from interfaces.website.site_connector import SiteConnector


@dataclass
class CreateLandingPageEffector(ConnectorEffectorBase):
    action_type: str = "create_landing_page"
    external_system: str = "site"
    connector: SiteConnector = field(default_factory=SiteConnector)
    operation: str = "create_landing_page"
