"""Marketplace and listing platform connector interfaces.

The implemented platform surface is intentionally reduced to Google Maps.
All other connector names exist only in the registry as explicit
not-implemented declarations.
"""

from .google_maps_connector import GoogleMapsConnector
from .registry import CONNECTORS

__all__ = ["GoogleMapsConnector", "CONNECTORS"]
