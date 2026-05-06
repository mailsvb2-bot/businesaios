from __future__ import annotations
CANON_ACTION_MAPPER_FINAL_OWNER = True


from dataclasses import dataclass

from entrypoints.api.action_models import ExecuteActionRequest


@dataclass(frozen=True)
class ApiAction:
    action_type: str
    payload: dict


def map_execute_action_request(request: ExecuteActionRequest) -> ApiAction:
    return ApiAction(
        action_type=request.action_type,
        payload=dict(request.payload),
    )
