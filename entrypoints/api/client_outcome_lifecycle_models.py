from __future__ import annotations

from typing import Any

from pydantic import BaseModel


CANON_CLIENT_OUTCOME_LIFECYCLE_API_MODELS = True


class ClientOutcomeLifecycleStagePayload(BaseModel):
    at: str
    payload: dict[str, Any]


class ClientOutcomeLifecycleResponse(BaseModel):
    found: bool
    order_id: str = ''
    lead_id: str = ''
    created_at: str = ''
    updated_at: str = ''
    stages: dict[str, ClientOutcomeLifecycleStagePayload] = {}
