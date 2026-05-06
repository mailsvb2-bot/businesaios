from __future__ import annotations

from crm.execution.crm_execution_result_mapper import CrmExecutionResultMapper
from crm.execution.crm_execution_router import CrmExecutionRouter


class CrmExecutionService:
    def __init__(self, router: CrmExecutionRouter | None = None, result_mapper: CrmExecutionResultMapper | None = None) -> None:
        self._router = router or CrmExecutionRouter()
        self._result_mapper = result_mapper or CrmExecutionResultMapper()

    def execute(self, action, *, handler_map: dict[str, object]) -> dict[str, object]:
        route = self._router.route(action)
        handler = handler_map[route]
        result = handler(action)
        return self._result_mapper.map(dict(result))
