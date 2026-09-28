TASK_CREATED = "task.created"
TASK_READY = "task.ready"
TASK_STARTED = "task.started"
TASK_WAITING = "task.waiting"
TASK_PAUSED = "task.paused"
TASK_BLOCKED = "task.blocked"
TASK_SUCCEEDED = "task.succeeded"
TASK_COMPLETED = "task.completed"  # legacy success fact accepted during migration
TASK_FAILED = "task.failed"
TASK_CANCELLED = "task.cancelled"
TASK_COMPENSATING = "task.compensating"
TASK_ARTIFACT_ATTACHED = "task.artifact_attached"
TASK_PREEMPTION_REQUESTED = "task.preemption_requested"

TASK_FACT_TYPES = frozenset(
    {
        TASK_CREATED,
        TASK_READY,
        TASK_STARTED,
        TASK_WAITING,
        TASK_PAUSED,
        TASK_BLOCKED,
        TASK_SUCCEEDED,
        TASK_COMPLETED,
        TASK_FAILED,
        TASK_CANCELLED,
        TASK_COMPENSATING,
        TASK_ARTIFACT_ATTACHED,
        TASK_PREEMPTION_REQUESTED,
    }
)

__all__ = [
    "TASK_ARTIFACT_ATTACHED",
    "TASK_BLOCKED",
    "TASK_CANCELLED",
    "TASK_COMPLETED",
    "TASK_COMPENSATING",
    "TASK_CREATED",
    "TASK_FACT_TYPES",
    "TASK_FAILED",
    "TASK_PAUSED",
    "TASK_PREEMPTION_REQUESTED",
    "TASK_READY",
    "TASK_STARTED",
    "TASK_SUCCEEDED",
    "TASK_WAITING",
]
