"""Honest reviews connector interfaces."""

from .google_reviews_connector import GoogleReviewsConnector
from .registry import CONNECTORS

__all__ = ["CONNECTORS", "GoogleReviewsConnector"]
