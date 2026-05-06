from __future__ import annotations

ALLOWED_FACTORY_MODULES: tuple[str, ...] = (
    "boot/factories/decision_core_factory.py",
    "boot/factories/governance_chain_factory.py",
    "boot/factories/action_executor_factory.py",
    "boot/registrations/register_decision_core.py",
    "boot/registrations/register_governance.py",
    "boot/registrations/register_action_executor.py",
)
