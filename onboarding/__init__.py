from __future__ import annotations

from shared.kinded_payloads import build_kinded_payload

CANON_ONBOARDING_ALIAS_NAMESPACE = True
CANON_ONBOARDING_PACKAGE_OWNER = True

class ActivationFlow:
    def build(self, payload: dict) -> dict:
        return build_kinded_payload("activation_flow", payload)

class AdsConnectionFlow:
    def build(self, payload: dict) -> dict:
        return build_kinded_payload("ads_connection_flow", payload)

class BusinessProfileCollector:
    def collect(self, payload: dict) -> dict:
        return build_kinded_payload("business_profile", payload)

class BusinessSetupFlow:
    def build(self, payload: dict) -> dict:
        return build_kinded_payload("business_setup_flow", payload)

class ChannelSetup:
    def build(self, payload: dict) -> dict:
        return build_kinded_payload("channel_setup", payload)

class CrmConnectionFlow:
    def build(self, payload: dict) -> dict:
        return build_kinded_payload("crm_connection_flow", payload)

class GoalSetup:
    def build(self, payload: dict) -> dict:
        return build_kinded_payload("goal_setup", payload)

class PlatformConnectionFlow:
    def build(self, payload: dict) -> dict:
        return build_kinded_payload("platform_connection_flow", payload)

class ReadinessCheck:
    def evaluate(self, payload: dict) -> dict:
        return build_kinded_payload("readiness_check", payload)

class WebsiteConnectionFlow:
    def build(self, payload: dict) -> dict:
        return build_kinded_payload("website_connection_flow", payload)

__all__ = [
    "CANON_ONBOARDING_ALIAS_NAMESPACE",
    "CANON_ONBOARDING_PACKAGE_OWNER",
    "ActivationFlow",
    "AdsConnectionFlow",
    "BusinessProfileCollector",
    "BusinessSetupFlow",
    "ChannelSetup",
    "CrmConnectionFlow",
    "GoalSetup",
    "PlatformConnectionFlow",
    "ReadinessCheck",
    "WebsiteConnectionFlow",
]
