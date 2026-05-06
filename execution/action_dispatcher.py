from __future__ import annotations
from contracts.action_result import ActionResult
from contracts.executable_action import ExecutableAction
from execution.action_validator import ActionValidator
from execution.action_runner import ActionRunner
from execution.run_result_store import ActionResultStore
from execution.action_idempotency import ActionIdempotency
from execution.dispatch_runner_chain import DispatchRunnerChain
from execution.dispatch_runtime import DispatchRuntime
from observability.action_audit_log import ActionAuditLog
from observability.metrics import CounterStore
from observability.tracing import Tracer


class ActionDispatcher:
    def __init__(
        self,
        validator: ActionValidator,
        runner: ActionRunner,
        store: ActionResultStore,
        audit_log: ActionAuditLog,
        idempotency: ActionIdempotency,
        metrics: CounterStore | None = None,
        tracer: Tracer | None = None,
    ) -> None:
        self._validator = validator
        self._runner = runner
        self._store = store
        self._audit_log = audit_log
        self._idempotency = idempotency
        self._metrics = metrics or CounterStore()
        self._tracer = tracer or Tracer()
        self._chain = DispatchRunnerChain(validator=self._validator, runner=self._runner, idempotency=self._idempotency)
        self._runtime = DispatchRuntime(
            chain=self._chain,
            store=self._store,
            audit_log=self._audit_log,
            metrics=self._metrics,
            tracer=self._tracer,
        )

    def dispatch(self, action: ExecutableAction) -> ActionResult:
        if not isinstance(action, ExecutableAction):
            raise TypeError('dispatch requires ExecutableAction')
        return self._runtime.dispatch(action)
