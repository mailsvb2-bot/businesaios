from __future__ import annotations

import time
from typing import Any

from application.campaign.projector import CAMPAIGN_ARCHIVED, CAMPAIGN_CREATED, CAMPAIGN_UPDATED, CampaignProjector
from application.ontology import EventFactLifecycleWriter
from contracts.campaign import Campaign, CampaignLifecycleStatus
from reliability.idempotency_contract import IdempotencyStore

CANON_CAMPAIGN_LIFECYCLE_OWNER = True


class CampaignRegistry:
    """Single PII-free Campaign lifecycle writer over the canonical EventStore."""

    def __init__(self, *, event_store: Any, idempotency_store: IdempotencyStore) -> None:
        self._projector = CampaignProjector(event_store)
        self._writer = EventFactLifecycleWriter(
            event_store=event_store,
            idempotency_store=idempotency_store,
            namespace="campaign_fact",
            source="campaign_registry",
            id_prefix="campaign",
        )

    @staticmethod
    def _time(value: int | None) -> int:
        return int(time.time() * 1000) if value is None else max(0, int(value))

    @staticmethod
    def _payload(campaign: Campaign) -> dict[str, object]:
        return {
            "channel_key": campaign.channel_key,
            "objective_key": campaign.objective_key,
            "budget_minor": campaign.budget_minor,
            "currency": campaign.currency,
        }

    @staticmethod
    def _state_token(campaign: Campaign) -> str:
        return "|".join((
            campaign.lifecycle_status.value,
            str(campaign.updated_at_ms),
            campaign.channel_key or "",
            campaign.objective_key or "",
            "" if campaign.budget_minor is None else str(campaign.budget_minor),
            campaign.currency or "",
        ))

    def create(
        self,
        *,
        tenant_id: str,
        business_id: str,
        campaign_id: str,
        idempotency_key: str,
        channel_key: str | None = None,
        objective_key: str | None = None,
        budget_minor: int | None = None,
        currency: str | None = None,
        occurred_at_ms: int | None = None,
    ) -> Campaign:
        when = self._time(occurred_at_ms)
        candidate = Campaign(
            campaign_id=campaign_id,
            tenant_id=tenant_id,
            business_id=business_id,
            channel_key=channel_key,
            objective_key=objective_key,
            budget_minor=budget_minor,
            currency=currency,
            created_at_ms=when,
            updated_at_ms=when,
        )
        payload = self._payload(candidate)
        try:
            current = self._projector.get(tenant_id=tenant_id, business_id=business_id, campaign_id=campaign_id)
        except LookupError:
            current = None
        if current is not None:
            if self._payload(current) != payload:
                raise ValueError("campaign already exists with different identity metadata")
            self._writer.repair_existing(
                tenant_id=tenant_id,
                business_id=business_id,
                entity_id=campaign_id,
                operation="create",
                idempotency_key=idempotency_key,
                fact_type=CAMPAIGN_CREATED,
                payload=payload,
            )
            return current
        self._writer.append_once(
            tenant_id=tenant_id,
            business_id=business_id,
            entity_id=campaign_id,
            operation="create",
            idempotency_key=idempotency_key,
            fact_type=CAMPAIGN_CREATED,
            payload=payload,
            occurred_at_ms=when,
        )
        return self._projector.get(tenant_id=tenant_id, business_id=business_id, campaign_id=campaign_id)

    def update(
        self,
        *,
        tenant_id: str,
        business_id: str,
        campaign_id: str,
        idempotency_key: str,
        channel_key: str | None = None,
        objective_key: str | None = None,
        budget_minor: int | None = None,
        currency: str | None = None,
        occurred_at_ms: int | None = None,
    ) -> Campaign:
        current = self._projector.get(tenant_id=tenant_id, business_id=business_id, campaign_id=campaign_id)
        if current.lifecycle_status is CampaignLifecycleStatus.ARCHIVED:
            raise ValueError("archived campaign cannot be updated")
        when = max(current.updated_at_ms, self._time(occurred_at_ms))
        candidate = Campaign(
            campaign_id=current.campaign_id,
            tenant_id=current.tenant_id,
            business_id=current.business_id,
            channel_key=current.channel_key if channel_key is None else channel_key,
            objective_key=current.objective_key if objective_key is None else objective_key,
            budget_minor=current.budget_minor if budget_minor is None else budget_minor,
            currency=current.currency if currency is None else currency,
            created_at_ms=current.created_at_ms,
            updated_at_ms=when,
        )
        if current.channel_key is not None and candidate.channel_key != current.channel_key:
            raise ValueError("campaign channel cannot be rewritten")
        if current.currency is not None and candidate.currency != current.currency:
            raise ValueError("campaign currency cannot be rewritten")
        payload = self._payload(candidate)
        if payload == self._payload(current):
            return current
        self._writer.append_transition_once(
            tenant_id=tenant_id,
            business_id=business_id,
            entity_id=campaign_id,
            expected_state_token=self._state_token(current),
            operation="update",
            idempotency_key=idempotency_key,
            fact_type=CAMPAIGN_UPDATED,
            payload=payload,
            occurred_at_ms=when,
        )
        return self._projector.get(tenant_id=tenant_id, business_id=business_id, campaign_id=campaign_id)

    def archive(
        self,
        *,
        tenant_id: str,
        business_id: str,
        campaign_id: str,
        idempotency_key: str,
        occurred_at_ms: int | None = None,
    ) -> Campaign:
        current = self._projector.get(tenant_id=tenant_id, business_id=business_id, campaign_id=campaign_id)
        if current.lifecycle_status is CampaignLifecycleStatus.ARCHIVED:
            return current
        when = max(current.updated_at_ms, self._time(occurred_at_ms))
        self._writer.append_transition_once(
            tenant_id=tenant_id,
            business_id=business_id,
            entity_id=campaign_id,
            expected_state_token=self._state_token(current),
            operation="archive",
            idempotency_key=idempotency_key,
            fact_type=CAMPAIGN_ARCHIVED,
            payload={},
            occurred_at_ms=when,
        )
        return self._projector.get(tenant_id=tenant_id, business_id=business_id, campaign_id=campaign_id)

    def get(self, *, tenant_id: str, business_id: str, campaign_id: str) -> Campaign:
        return self._projector.get(tenant_id=tenant_id, business_id=business_id, campaign_id=campaign_id)

    def list_for_business(self, *, tenant_id: str, business_id: str) -> tuple[Campaign, ...]:
        return self._projector.list_for_business(tenant_id=tenant_id, business_id=business_id)


__all__ = ["CANON_CAMPAIGN_LIFECYCLE_OWNER", "CampaignRegistry"]
