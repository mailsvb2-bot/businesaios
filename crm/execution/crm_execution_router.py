from __future__ import annotations

from crm.execution.crm_action_dispatcher import CrmActionDispatcher


class CrmExecutionRouter:
    def __init__(self, dispatcher: CrmActionDispatcher | None = None) -> None:
        self._dispatcher = dispatcher or CrmActionDispatcher()

    def route(self, action) -> str:
        return self._dispatcher.dispatch(action)
