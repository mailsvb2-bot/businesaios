from __future__ import annotations

from interfaces.telegram.outbound.outbound_self_heal import SelfHealConfig


def build_self_heal_config(
    *,
    enabled: bool,
    cooldown_s: float,
    on_sla: bool,
    on_qsize: bool,
    on_drops: bool,
    purge_enabled: bool,
    purge_max_items: int,
    purge_blacklist: tuple[str, ...] | None,
    purge_whitelist: tuple[str, ...] | None,
) -> SelfHealConfig:
    return SelfHealConfig(
        enabled=bool(enabled),
        cooldown_ns=int(float(cooldown_s) * 1e9),
        on_sla=bool(on_sla),
        on_qsize=bool(on_qsize),
        on_drops=bool(on_drops),
        purge_enabled=bool(purge_enabled),
        purge_max_items=int(purge_max_items),
        purge_blacklist=tuple(
            k.strip().lower()
            for k in (purge_blacklist or ("marketing", "bulk", "analytics"))
            if str(k).strip()
        ),
        purge_whitelist=tuple(
            k.strip().lower()
            for k in (purge_whitelist or ("ux", "system", "payments", "ack"))
            if str(k).strip()
        ),
    )
