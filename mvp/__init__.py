"""MVP package."""
from __future__ import annotations

from shared.kinded_payloads import build_kinded_payload

class LocalServicesProfile:
    def build(self, payload: dict) -> dict:
        return build_kinded_payload("local_services_profile", payload)

class MetaGoogleLeadsMode:
    def build(self, payload: dict) -> dict:
        return build_kinded_payload("meta_google_leads_mode", payload)

class MvpActivation:
    def activate(self, payload: dict) -> dict:
        return build_kinded_payload("mvp_activation", payload)

class MvpConstraints:
    def build(self, payload: dict) -> dict:
        return build_kinded_payload("mvp_constraints", payload)

class MvpFeedback:
    def build(self, payload: dict) -> dict:
        return build_kinded_payload("mvp_feedback", payload)

class MvpReadiness:
    def evaluate(self, payload: dict) -> dict:
        return build_kinded_payload("mvp_readiness", payload)

__all__ = ["LocalServicesProfile", "MetaGoogleLeadsMode", "MvpActivation", "MvpConstraints", "MvpFeedback", "MvpReadiness"]
