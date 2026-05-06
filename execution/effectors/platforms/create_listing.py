from __future__ import annotations

from dataclasses import dataclass, field

from execution.effectors.base import ConnectorEffectorBase
from interfaces.platforms.google_maps_connector import GoogleMapsConnector


@dataclass
class CreateListingEffector(ConnectorEffectorBase):
    action_type: str = "create_listing"
    external_system: str = "google_maps"
    connector: GoogleMapsConnector = field(default_factory=GoogleMapsConnector)
    operation: str = "create_listing"
