from __future__ import annotations

import runtime.execution.executor_trace_runtime as trace_runtime
from runtime.decision import DecisionEnvelope
from runtime.execution.context import assert_called_from_executor, executor_context
from runtime.execution.executor_autonomy_gate import (
    deny_autonomy_execution as executor_deny_autonomy_execution,
)
from runtime.execution.executor_autonomy_gate import (
    enforce_runtime_budget_and_blast_radius as executor_enforce_runtime_budget_and_blast_radius,
)
from runtime.execution.executor_autonomy_gate import (
    ensure_tenant_runtime_contracts as executor_ensure_tenant_runtime_contracts,
)
from runtime.execution.executor_autonomy_gate import (
    tenant_runtime_context as executor_tenant_runtime_context,
)
from runtime.execution.executor_queue_runtime import (
    campaign_or_heartbeat_recovery_leader as executor_campaign_or_heartbeat_recovery_leader,
)
from runtime.execution.executor_queue_runtime import (
    campaign_or_heartbeat_scheduler_leader as executor_campaign_or_heartbeat_scheduler_leader,
)
from runtime.execution.executor_queue_runtime import (
    campaign_recovery_leader as executor_campaign_recovery_leader,
)
from runtime.execution.executor_queue_runtime import (
    campaign_scheduler_leader as executor_campaign_scheduler_leader,
)
from runtime.execution.executor_queue_runtime import (
    enqueue_runtime_job as executor_enqueue_runtime_job,
)
from runtime.execution.executor_queue_runtime import (
    run_queue_tick as executor_run_queue_tick,
)
from runtime.execution.executor_queue_runtime import (
    run_queue_tick_as_leader as executor_run_queue_tick_as_leader,
)
from runtime.execution.executor_stages import dispatch_effects
from runtime.execution.executor_stages import preflight_and_verify as _preflight_and_verify


def preflight_and_verify(*args, **kwargs):
    return _preflight_and_verify(*args, **kwargs)


def execute_core_flow(*, executor, env, depth, timescale):
    return trace_runtime.execute_core_flow(
        executor=executor,
        env=env,
        depth=depth,
        timescale=timescale,
        preflight_fn=preflight_and_verify,
    )


def _ensure_tenant_runtime_contracts(self, tenant_id: str) -> None:
    executor_ensure_tenant_runtime_contracts(executor=self, tenant_id=tenant_id)


def _tenant_runtime_context(self, *, env: DecisionEnvelope, payload):
    return executor_tenant_runtime_context(executor=self, env=env, payload=payload)


def _deny_autonomy_execution(self, *, env: DecisionEnvelope, reason: str, payload=None) -> None:
    executor_deny_autonomy_execution(executor=self, env=env, reason=reason, payload=payload)


def _enforce_runtime_budget_and_blast_radius(self, env: DecisionEnvelope):
    return executor_enforce_runtime_budget_and_blast_radius(executor=self, env=env)


def _dispatch(self, env: DecisionEnvelope, *, depth: int, enqueue: bool):
    return dispatch_effects(executor=self, env=env, depth=depth, enqueue=enqueue)


def enqueue_runtime_job(self, request):
    return executor_enqueue_runtime_job(executor=self, request=request)


def run_queue_tick(self, *, tenant_id: str, queue_name: str, now=None):
    return executor_run_queue_tick(executor=self, tenant_id=tenant_id, queue_name=queue_name, now=now)


def campaign_scheduler_leader(self, *, tenant_id: str, owner_id: str, ttl_seconds: int | None = None, now=None):
    return executor_campaign_scheduler_leader(executor=self, tenant_id=tenant_id, owner_id=owner_id, ttl_seconds=ttl_seconds, now=now)


def campaign_or_heartbeat_scheduler_leader(self, *, tenant_id: str, owner_id: str, ttl_seconds: int | None = None, now=None):
    return executor_campaign_or_heartbeat_scheduler_leader(executor=self, tenant_id=tenant_id, owner_id=owner_id, ttl_seconds=ttl_seconds, now=now)


def campaign_recovery_leader(self, *, tenant_id: str, owner_id: str, ttl_seconds: int | None = None, now=None):
    return executor_campaign_recovery_leader(executor=self, tenant_id=tenant_id, owner_id=owner_id, ttl_seconds=ttl_seconds, now=now)


def campaign_or_heartbeat_recovery_leader(self, *, tenant_id: str, owner_id: str, ttl_seconds: int | None = None, now=None):
    return executor_campaign_or_heartbeat_recovery_leader(executor=self, tenant_id=tenant_id, owner_id=owner_id, ttl_seconds=ttl_seconds, now=now)


def run_queue_tick_as_leader(self, *, tenant_id: str, queue_name: str, owner_id: str, ttl_seconds: int | None = None, now=None):
    return executor_run_queue_tick_as_leader(
        executor=self,
        tenant_id=tenant_id,
        queue_name=queue_name,
        owner_id=owner_id,
        ttl_seconds=ttl_seconds,
        now=now,
    )


__all__ = [
    'preflight_and_verify',
    'execute_core_flow',
    'executor_context',
    'assert_called_from_executor',
    '_ensure_tenant_runtime_contracts',
    '_tenant_runtime_context',
    '_deny_autonomy_execution',
    '_enforce_runtime_budget_and_blast_radius',
    '_dispatch',
    'enqueue_runtime_job',
    'run_queue_tick',
    'campaign_scheduler_leader',
    'campaign_or_heartbeat_scheduler_leader',
    'campaign_recovery_leader',
    'campaign_or_heartbeat_recovery_leader',
    'run_queue_tick_as_leader',
]


def build_sealed_commercial_merchant_bundle(**kwargs):
    from runtime.executor import build_sealed_commercial_merchant_bundle as compose

    return compose(**kwargs)


def _sealed_stars_merchant(*, transport=None):
    """Bind one real Bot API identity and explicit merchant signing key."""
    from runtime._internal.effects_clients.telegram_client import TelegramClient
    from runtime.platform.config.env_flags import env_str

    signing_key = env_str("TELEGRAM_STARS_SIGNING_KEY", "").encode("utf-8")
    if len(signing_key) < 32:
        raise RuntimeError("commercial_stars_signing_key_missing")
    client = TelegramClient(transport=transport)
    bot = client.get_me()
    bot_user = bot.get("result") if isinstance(bot, dict) and bot.get("ok") is True else None
    bot_id = bot_user.get("id") if isinstance(bot_user, dict) else None
    if type(bot_id) is not int or bot_id <= 0 or bot_user.get("is_bot") is not True:
        raise RuntimeError("commercial_stars_bot_identity_unverified")
    return client, str(bot_id), signing_key


def build_sealed_stars_commercial_merchant_bundle(
    *, purchases, event_store, idempotency_store, payer_resolver, transport=None,
):
    """Executor-owned Stars effects, canonical payment/entitlement state."""
    from application.commerce.phase18_commercial_checkout import (
        build_telegram_stars_commercial_bundle,
    )

    client, bot_id, key = _sealed_stars_merchant(transport=transport)
    return build_telegram_stars_commercial_bundle(
        purchases=purchases, event_store=event_store,
        idempotency_store=idempotency_store, bot_id=bot_id,
        signing_secret=key, payer_resolver=payer_resolver,
        sealed_create_invoice_link=client.create_stars_invoice_link,
        sealed_read_transactions=client.list_stars_transactions,
    )


def build_sealed_dual_commercial_merchant_bundle(
    *, purchases, event_store, idempotency_store, payer_resolver, transport=None,
):
    """RUB and XTR have separate verified providers but only one Billing owner."""
    from functools import partial

    from application.commerce.phase18_commercial_checkout import (
        build_dual_commercial_merchant_bundle,
    )
    from runtime._internal.effects_clients.yookassa_client import (
        create_merchant_payment,
        fetch_merchant_payment,
        resolve_credentials,
    )

    merchant_id, secret, api = resolve_credentials()
    if not merchant_id or not secret:
        raise RuntimeError("commercial_merchant_configuration_missing")
    client, bot_id, key = _sealed_stars_merchant(transport=transport)
    return build_dual_commercial_merchant_bundle(
        purchases=purchases, event_store=event_store,
        idempotency_store=idempotency_store, merchant_id=merchant_id,
        sealed_create_payment=partial(create_merchant_payment, transport=transport),
        sealed_fetch_payment=partial(fetch_merchant_payment, transport=transport),
        bot_id=bot_id, signing_secret=key, payer_resolver=payer_resolver,
        sealed_create_invoice_link=client.create_stars_invoice_link,
        sealed_read_transactions=client.list_stars_transactions,
    )
