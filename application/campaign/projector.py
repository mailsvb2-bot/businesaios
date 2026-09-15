from __future__ import annotations

from dataclasses import replace
from typing import Any

from application.campaign.facts import CAMPAIGN_ARCHIVED, CAMPAIGN_CREATED, CAMPAIGN_FACT_TYPES, CAMPAIGN_UPDATED
from contracts.campaign import Campaign, CampaignLifecycleStatus, CampaignNotFound
from contracts.event_store import BUSINESS_FACT_EVENT_TYPE

CANON_CAMPAIGN_PROJECTOR = True


class CampaignHistoryInvariantViolation(RuntimeError):
    pass


class CampaignProjector:
    def __init__(self, event_store: Any) -> None:
        self._events = event_store

    def _facts(self, *, tenant_id: str, business_id: str, campaign_id: str | None = None) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for append_order, event in enumerate(
            self._events.iter_events(tenant_id=str(tenant_id), start_ms=0, event_type=BUSINESS_FACT_EVENT_TYPE)
        ):
            envelope = dict(event.get("payload") or {})
            if str(envelope.get("business_id") or "") != str(business_id):
                continue
            fact_type = str(envelope.get("fact_type") or "")
            entity_id = str(envelope.get("entity_id") or "")
            if fact_type not in CAMPAIGN_FACT_TYPES or (campaign_id is not None and entity_id != str(campaign_id)):
                continue
            rows.append({
                "fact_id": str(event.get("event_id") or ""),
                "fact_type": fact_type,
                "entity_id": entity_id,
                "event_time_ms": int(envelope.get("event_time_ms") or event.get("timestamp_ms") or 0),
                "observed_at_ms": int(envelope.get("observed_at_ms") or event.get("timestamp_ms") or 0),
                "append_order": append_order,
                "payload": dict(envelope.get("payload") or {}),
            })
        rows.sort(key=lambda row: (row["event_time_ms"], row["observed_at_ms"], row["append_order"], row["fact_id"]))
        return rows

    def get(self, *, tenant_id: str, business_id: str, campaign_id: str) -> Campaign:
        facts = self._facts(tenant_id=tenant_id, business_id=business_id, campaign_id=campaign_id)
        if not facts:
            raise CampaignNotFound(f"campaign not found: {campaign_id}")
        created_rows = [row for row in facts if row["fact_type"] == CAMPAIGN_CREATED]
        if len(created_rows) != 1 or facts[0] is not created_rows[0]:
            raise CampaignHistoryInvariantViolation("campaign history must begin with exactly one create fact")
        created = created_rows[0]
        payload = dict(created["payload"])
        campaign = Campaign(
            campaign_id=str(campaign_id), tenant_id=str(tenant_id), business_id=str(business_id),
            channel_key=payload.get("channel_key"), objective_key=payload.get("objective_key"),
            budget_minor=payload.get("budget_minor"), currency=payload.get("currency"),
            created_at_ms=int(created["event_time_ms"]), updated_at_ms=int(created["event_time_ms"]),
        )
        for row in facts[1:]:
            if campaign.lifecycle_status is CampaignLifecycleStatus.ARCHIVED:
                raise CampaignHistoryInvariantViolation("campaign history continues after archive")
            when = int(row["event_time_ms"])
            if row["fact_type"] == CAMPAIGN_UPDATED:
                update = dict(row["payload"])
                next_channel = update.get("channel_key", campaign.channel_key)
                next_currency = update.get("currency", campaign.currency)
                if campaign.channel_key is not None and next_channel != campaign.channel_key:
                    raise CampaignHistoryInvariantViolation("campaign channel cannot be rewritten")
                if campaign.currency is not None and next_currency != campaign.currency:
                    raise CampaignHistoryInvariantViolation("campaign currency cannot be rewritten")
                campaign = replace(
                    campaign,
                    channel_key=next_channel,
                    objective_key=update.get("objective_key", campaign.objective_key),
                    budget_minor=update.get("budget_minor", campaign.budget_minor),
                    currency=next_currency,
                    updated_at_ms=max(campaign.updated_at_ms, when),
                )
            elif row["fact_type"] == CAMPAIGN_ARCHIVED:
                campaign = replace(
                    campaign, lifecycle_status=CampaignLifecycleStatus.ARCHIVED,
                    updated_at_ms=max(campaign.updated_at_ms, when), archived_at_ms=when,
                )
        return campaign

    def list_for_business(self, *, tenant_id: str, business_id: str) -> tuple[Campaign, ...]:
        ids = sorted({str(row["entity_id"]) for row in self._facts(tenant_id=tenant_id, business_id=business_id)})
        return tuple(self.get(tenant_id=tenant_id, business_id=business_id, campaign_id=value) for value in ids)


__all__ = ["CANON_CAMPAIGN_PROJECTOR", "CampaignHistoryInvariantViolation", "CampaignProjector"]
