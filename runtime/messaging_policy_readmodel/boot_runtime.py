from __future__ import annotations

from runtime._safe_setattr import safe_setattr
from runtime.messaging_policy_readmodel.boot_dependencies import build_messaging_policy_read_services


def boot_messaging_policy_readmodel(*, runtime_obj, event_store):
    services = build_messaging_policy_read_services(event_store=event_store)
    safe_setattr(runtime_obj, "messaging_policy_snapshot_store", services["store"])
    safe_setattr(runtime_obj, "messaging_policy_snapshot_repository", services["repository"])
    safe_setattr(runtime_obj, "messaging_policy_read_service", services["read_service"])
    return services
