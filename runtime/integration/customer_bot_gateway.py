"""Customer (managed) bot gateway runtime: polls every COMPLETED tenant bot and feeds updates into
the one canonical decision path; replies go out with that bot's token via the delivery-token scope.

Port of the donor ``runtime/bot_gateway.ManagedBotGatewayRuntime`` without aiogram or a second
dispatcher: polling reuses ``poll_telegram_updates_effect(token=)``, decisions stay in DecisionCore.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable
from typing import Any

from application.business_flows import bot_gateway as gw

Poll = Callable[..., Any]
Dispatch = Callable[[dict[str, Any], gw.Route], None]


class CustomerBotGateway:
    def __init__(
        self,
        *,
        config: gw.GatewayConfig,
        routes: Callable[[], Iterable[gw.Route]],
        resolve_token: Callable[[gw.Route], str],
        dispatch: Dispatch,
        poll: Poll,
        token_scope: Callable[[str], Any],
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.config = config
        self._routes, self._resolve, self._dispatch = routes, resolve_token, dispatch
        self._poll, self._scope, self._clock = poll, token_scope, clock
        self._admission = gw.Admission(config)
        self._offsets: dict[str, int] = {}
        self._failures: dict[tuple[str, int], int] = {}
        self.stats = {"ticks": 0, "polled": 0, "admitted": 0, "duplicates": 0, "rejected": 0,
                      "processed": 0, "retried": 0, "dead": 0, "poll_errors": 0, "last_error": ""}  # fmt: skip

    def tick(self) -> int:
        """One pass over active routes; returns processed updates. Disabled config is a no-op."""
        if not self.config.enabled:
            return 0
        self.stats["ticks"] += 1
        processed = 0
        active = list(self._routes())
        live = {r.external_bot_id for r in active}
        for bot_id in [b for b in self._offsets if b not in live]:  # revoked/disabled: forget offset
            self._offsets.pop(bot_id)
        for route in active:
            processed += self._poll_route(route)
        return processed

    def _poll_route(self, route: gw.Route) -> int:
        try:
            token = self._resolve(route)
        except Exception as exc:  # noqa: BLE001 - secret-adjacent; code only
            return self._error("credential_" + gw.safe_error_code(exc))
        if not token:
            return self._error("credential_unresolved")
        res = self._poll(token=token, offset=self._offsets.get(route.external_bot_id), timeout_s=0,
                         limit=self.config.poll_limit)  # fmt: skip
        if not isinstance(res, dict) or res.get("ok") is not True:
            return self._error("poll_failed")
        done = 0
        for payload in res.get("updates") or []:
            if not isinstance(payload, dict):
                continue
            verdict = self._admission.admit(route, payload, now_s=self._clock())
            self.stats["polled"] += 1
            if verdict == "duplicate":
                self.stats["duplicates"] += 1
            elif verdict.startswith("rejected"):
                self.stats["rejected"] += 1
                self.stats["last_error"] = verdict
                if verdict == "rejected:update_id_required":
                    continue
                break  # rate/queue/size: keep offset so the update is re-delivered later
            else:
                self.stats["admitted"] += 1
                if not self._process(route, payload, token):
                    break  # retry from this update on the next tick
                done += 1
            self._offsets[route.external_bot_id] = int(payload["update_id"]) + 1
        return done

    def _process(self, route: gw.Route, payload: dict[str, Any], token: str) -> bool:
        key = (route.external_bot_id, int(payload["update_id"]))
        try:
            with self._scope(token):
                self._dispatch(payload, route)
        except Exception as exc:  # noqa: BLE001 - one poison update must not stall the bot forever
            self._admission.done(route)
            self._admission._seen.get(route.external_bot_id, set()).discard(key[1])
            attempts = self._failures[key] = self._failures.get(key, 0) + 1
            self.stats["last_error"] = gw.safe_error_code(exc)
            if attempts < self.config.max_attempts:
                self.stats["retried"] += 1
                return False
            self._failures.pop(key, None)
            self.stats["dead"] += 1
            return True
        self._admission.done(route)
        self._failures.pop(key, None)
        self.stats["processed"] += 1
        return True

    def _error(self, code: str) -> int:
        self.stats["poll_errors"] += 1
        self.stats["last_error"] = code
        return 0

    def health_snapshot(self) -> dict[str, Any]:
        return {"enabled": self.config.enabled, "transport": "polling", "active_offsets": len(self._offsets),
                **self.stats}  # fmt: skip


def build_customer_bot_gateway(
    *, event_store: Any, tenant_id: str, dispatch: Dispatch, env: dict[str, str], vault: Any = None
) -> CustomerBotGateway | None:
    """Production wiring; None unless CUSTOMER_BOT_GATEWAY_ENABLED and an event store exist."""
    config = gw.gateway_config(env)
    if not config.enabled or event_store is None:
        return None
    from application.business_flows import bot_provisioning as botprov
    from application.business_flows.projection import flow_payloads
    from runtime.effects import customer_bot_token_scope, poll_customer_bot_updates
    from runtime.integration import managed_bot_credentials as mbc

    if vault is None:
        try:
            from security.secret_vault import build_default_secret_vault

            vault = build_default_secret_vault()
        except Exception:  # noqa: BLE001 - vault refs then fail closed per route
            vault = None

    def routes() -> list[gw.Route]:
        payloads = flow_payloads(event_store, tenant_id=tenant_id, event_type="bot_provisioning@v1")
        return gw.active_routes(botprov.replay(payloads), tenant_id=tenant_id)

    def resolve(route: gw.Route) -> str:
        return str(mbc.resolve(route.credential_ref, tenant_id=route.tenant_id, vault=vault) or "").strip()

    return CustomerBotGateway(config=config, routes=routes, resolve_token=resolve, dispatch=dispatch,
                              poll=poll_customer_bot_updates, token_scope=customer_bot_token_scope)  # fmt: skip


__all__ = ["CustomerBotGateway", "build_customer_bot_gateway"]
