from __future__ import annotations

import time
from typing import Any

from application.ontology import EventFactLifecycleWriter
from application.public_site.landing_content import EventLandingContent, EventLandingPublicationStatus, EventLandingState

_CREATED="event_landing.created"; _DRAFT="event_landing.draft_saved"; _PUBLISHED="event_landing.published"; _UNPUBLISHED="event_landing.unpublished"
_FACTS=frozenset({_CREATED,_DRAFT,_PUBLISHED,_UNPUBLISHED})


class EventLandingRegistry:
    def __init__(self, *, event_store: Any, idempotency_store) -> None:
        self._events=event_store
        self._writer=EventFactLifecycleWriter(event_store=event_store,idempotency_store=idempotency_store,namespace="event_landing",source="event_landing_registry",id_prefix="event-landing")

    def _history(self, *, tenant_id: str, business_id: str, event_id: str) -> list[dict[str,object]]:
        rows=[]
        for order,event in enumerate(self._events.iter_events(tenant_id=tenant_id,start_ms=0,event_type="business.fact.v1")):
            envelope=dict(event.get("payload") or {})
            if envelope.get("business_id")!=business_id or envelope.get("entity_id")!=event_id or envelope.get("fact_type") not in _FACTS: continue
            rows.append({"type":envelope["fact_type"],"payload":dict(envelope.get("payload") or {}),"time":int(envelope.get("event_time_ms") or event.get("timestamp_ms") or 0),"order":order})
        rows.sort(key=lambda x:(x["time"],x["order"]))
        return rows

    def get(self, *, tenant_id: str, business_id: str, event_id: str) -> EventLandingState:
        rows=self._history(tenant_id=tenant_id,business_id=business_id,event_id=event_id)
        if not rows or rows[0]["type"]!=_CREATED: raise KeyError("event_landing_not_found")
        p=dict(rows[0]["payload"]); state=EventLandingState(event_id=event_id,draft=EventLandingContent.from_payload(p["content"]),draft_source=str(p["source"]),revision=1)
        for row in rows[1:]:
            p=dict(row["payload"]); expected=int(p["expected_revision"])
            if row["type"]==_DRAFT: state=state.save_draft(content=EventLandingContent.from_payload(p["content"]),source=str(p["source"]),expected_revision=expected)
            elif row["type"]==_PUBLISHED: state=state.publish(expected_revision=expected)
            elif row["type"]==_UNPUBLISHED: state=state.unpublish(expected_revision=expected)
        return state

    @staticmethod
    def _now() -> int: return int(time.time()*1000)

    def create(self, *, tenant_id: str, business_id: str, event_id: str, content: EventLandingContent, source: str, idempotency_key: str, actor_id: str) -> EventLandingState:
        try: current=self.get(tenant_id=tenant_id,business_id=business_id,event_id=event_id)
        except KeyError: current=None
        payload={"content":content.to_payload(),"source":source}
        if current is not None:
            self._writer.repair_existing(tenant_id=tenant_id,business_id=business_id,entity_id=event_id,operation="create",idempotency_key=idempotency_key,fact_type=_CREATED,payload=payload,event_metadata={"actor_id":actor_id})
            return current
        self._writer.append_once(tenant_id=tenant_id,business_id=business_id,entity_id=event_id,operation="create",idempotency_key=idempotency_key,fact_type=_CREATED,payload=payload,occurred_at_ms=self._now(),event_metadata={"actor_id":actor_id})
        return self.get(tenant_id=tenant_id,business_id=business_id,event_id=event_id)

    def transition(self, *, tenant_id: str, business_id: str, event_id: str, action: str, expected_revision: int, idempotency_key: str, actor_id: str, content: EventLandingContent|None=None, source: str="manual") -> EventLandingState:
        state=self.get(tenant_id=tenant_id,business_id=business_id,event_id=event_id)
        if expected_revision!=state.revision: raise RuntimeError("event_landing_revision_conflict")
        if action=="save":
            if content is None: raise ValueError("content_required")
            fact_type,payload=_DRAFT,{"expected_revision":expected_revision,"content":content.to_payload(),"source":source}
        elif action=="publish": fact_type,payload=_PUBLISHED,{"expected_revision":expected_revision}
        elif action=="unpublish": fact_type,payload=_UNPUBLISHED,{"expected_revision":expected_revision}
        else: raise ValueError("unsupported_event_landing_action")
        token=f"{state.revision}:{state.status.value}:{state.published_revision or 0}"
        self._writer.append_transition_once(tenant_id=tenant_id,business_id=business_id,entity_id=event_id,expected_state_token=token,operation=action,idempotency_key=idempotency_key,fact_type=fact_type,payload=payload,occurred_at_ms=self._now(),event_metadata={"actor_id":actor_id})
        return self.get(tenant_id=tenant_id,business_id=business_id,event_id=event_id)


def event_landing_payload(state: EventLandingState) -> dict[str,object]:
    return {"event_id":state.event_id,"revision":state.revision,"status":state.status.value,"draft_source":state.draft_source,"has_unpublished_changes":state.has_unpublished_changes,"draft":state.draft.to_payload(),"published":None if state.public_content() is None else state.public_content().to_payload(),"published_revision":state.published_revision}
