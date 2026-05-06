from __future__ import annotations

from dataclasses import dataclass

from contracts.action_impact_contract import ActionCategory, ActionExecutionContext
from core.safety.operational.action_registry import OperationalActionRegistry
from core.safety.operational.action_spec import ActionOperationalSpec


CANON_OPERATIONAL_ACTION_CLASSIFIER = True


@dataclass(frozen=True)
class ClassifiedAction:
    spec: ActionOperationalSpec
    action_name: str
    category: ActionCategory
    is_known: bool = True


class ActionClassifier:
    """
    Canonical classifier.

    This classifier must not infer semantics from action name prefixes.
    It only trusts declarative registry specs.
    Unknown actions fail closed.
    """

    def __init__(self, registry: OperationalActionRegistry) -> None:
        self._registry = registry

    def classify(self, ctx: ActionExecutionContext) -> ClassifiedAction:
        ctx.validate()
        spec = self._registry.get(ctx.action_name)
        if spec is None:
            unknown = ActionOperationalSpec(
                action_name=ctx.action_name,
                category=ActionCategory.UNKNOWN,
                requires_human_approval=True,
            )
            unknown.validate()
            return ClassifiedAction(
                spec=unknown,
                action_name=ctx.action_name,
                category=unknown.category,
                is_known=False,
            )
        spec.validate()
        return ClassifiedAction(
            spec=spec,
            action_name=ctx.action_name,
            category=spec.category,
            is_known=True,
        )


__all__ = [
    "ActionClassifier",
    "ClassifiedAction",
]