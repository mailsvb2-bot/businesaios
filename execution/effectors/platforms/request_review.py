from __future__ import annotations

from dataclasses import dataclass, field

from execution.effectors.base import ConnectorEffectorBase
from interfaces.reviews.google_reviews_connector import GoogleReviewsConnector


@dataclass
class RequestReviewEffector(ConnectorEffectorBase):
    action_type: str = "request_review"
    external_system: str = "google_reviews"
    connector: GoogleReviewsConnector = field(default_factory=GoogleReviewsConnector)
    operation: str = "request_review"
