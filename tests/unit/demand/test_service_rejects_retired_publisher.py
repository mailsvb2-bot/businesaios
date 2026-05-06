from __future__ import annotations

import pytest

from contracts.supply import BusinessLiveState
from contracts.supply import BusinessSupplyProfile
from demand_capture.demand_capture_service import DemandCaptureService
from demand_os.demand_os_service import DemandOperatingSystemService
from intent.client_intent_builder import ClientIntentBuilder
from matching.match_engine import MatchEngine
from routing.demand_router import DemandRouter
from routing_execution.lead_delivery_dispatcher import LeadDeliveryDispatcher


class Directory:
    def list_profiles(self):
        return (BusinessSupplyProfile(business_id='biz-1', active=True, notification_channels=('email',)),)

    def get_profile(self, business_id: str):
        return BusinessSupplyProfile(business_id=business_id, active=True, notification_channels=('email',))


class StateBuilder:
    def build(self, business_id: str):
        return BusinessLiveState(business_id=business_id, open_now=True, capacity_score=0.8, response_speed_score=0.8, conversion_score=0.8, quality_score=0.8, risk_score=0.1, reputation_score=0.8, margin_score=0.7)


class RetiredPublisher:
    def publish(self):
        raise RuntimeError('retired')


def test_service_rejects_retired_publisher_wiring() -> None:
    with pytest.raises(ValueError):
        DemandOperatingSystemService(
            demand_capture_service=DemandCaptureService(),
            client_intent_builder=ClientIntentBuilder(),
            business_live_state_builder=StateBuilder(),
            business_directory=Directory(),
            match_engine=MatchEngine(),
            demand_router=DemandRouter(business_directory=Directory(), business_live_state_builder=StateBuilder()),
            demand_decision_publisher=RetiredPublisher(),
            decision_core=None,
            lead_delivery_dispatcher=LeadDeliveryDispatcher(),
        )
