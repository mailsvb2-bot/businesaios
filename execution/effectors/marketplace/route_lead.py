from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from collections.abc import Mapping

from execution.effectors.base import EffectorBase
from execution.effectors.result import EffectorResult


@dataclass
class RouteLeadEffector(EffectorBase):
    action_type: str = "route_lead"
    external_system: str = "marketplace"

    def execute(self, action: Mapping[str, Any]) -> EffectorResult:
        payload = self._payload(action)
        lead_id = str(payload.get("lead_id") or payload.get("inquiry_id") or action.get("action_id") or "")
        target_business = str(payload.get("business_id") or payload.get("target_business_id") or "")
        matched = bool(lead_id and target_business)
        base_payload = {"lead_id": lead_id, "target_business_id": target_business}
        if not matched:
            return EffectorResult(
                attempted=True,
                executed=False,
                verified=False,
                status="operator_required",
                external_system=self.external_system,
                external_ref=self._action_ref(action),
                code="connector_not_available",
                message="route target missing or routing connector not available",
                operator_required=True,
                retry_kind="operator_required",
                payload=base_payload,
                evidence={
                    "action_type": self.action_type,
                    "lead_id": lead_id,
                    "target_business_id": target_business,
                    "routing_verified": False,
                    "simulated": False,
                },
            )
        return EffectorResult(
            attempted=True,
            executed=False,
            verified=False,
            status="operator_required",
            external_system=self.external_system,
            external_ref=self._action_ref(action),
            code="routing_connector_missing",
            message="routing request assembled but no external routing connector+verify path is wired",
            operator_required=True,
            retry_kind="operator_required",
            payload={**base_payload, "simulated": False},
            evidence={
                "action_type": self.action_type,
                "lead_id": lead_id,
                "target_business_id": target_business,
                "routing_verified": False,
                "routing_request_assembled": True,
                "simulated": False,
            },
        )
