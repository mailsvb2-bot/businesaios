from __future__ import annotations

"""Auto-deploy guardrails.

This module is an *operator safety layer*.
It does not decide what is best; it only enforces hard constraints for
automatic deployment/rollback proposals.

No side-effects.
"""

import time
from dataclasses import dataclass
from typing import Optional

from runtime.platform.config.env_flags import env_bool, env_int, env_str


@dataclass(frozen=True)
class AutoDeployVerdict:
    ok: bool
    reason: str
    rollout_pct: int | None = None


class AutoDeployGuard:
    def __init__(
        self,
        *,
        min_interval_s: int = 3600,
        max_rollout_pct: int = 10,
    ) -> None:
        self._min_interval_s = int(min_interval_s)
        self._max_rollout_pct = int(max_rollout_pct)
        self._last_deploy_ms: int = 0

    def _env(self) -> str:
        return env_str("APP_ENV", env_str("ENV", "dev")).lower()

    def allow(self, *, proposal: dict) -> AutoDeployVerdict:
        kind = str((proposal or {}).get("kind") or "")
        if kind not in {"deploy", "rollback"}:
            return AutoDeployVerdict(ok=False, reason="unknown_kind")

        env = self._env()

        # In production, auto-deploy must be explicitly enabled.
        if env == "prod" and kind == "deploy":
            if not env_bool("ENABLE_AUTODEPLOY", False):
                return AutoDeployVerdict(ok=False, reason="autodeploy_disabled")

        # Global cooldown (prevents thrashing).
        now_ms = int(time.time() * 1000)
        if kind == "deploy":
            if self._last_deploy_ms and (now_ms - self._last_deploy_ms) < int(self._min_interval_s * 1000):
                return AutoDeployVerdict(ok=False, reason="cooldown")

        # Clamp rollout percentage to a safe maximum.
        pct = proposal.get("rollout_pct", 10)
        try:
            pct_i = int(pct)
        except Exception:
            pct_i = 10
        pct_i = max(1, min(int(self._max_rollout_pct), pct_i))

        if kind == "deploy" and not proposal.get("candidate_policy_id"):
            return AutoDeployVerdict(ok=False, reason="missing_candidate")

        return AutoDeployVerdict(ok=True, reason="ok", rollout_pct=pct_i)

    def note_deploy_executed(self) -> None:
        self._last_deploy_ms = int(time.time() * 1000)


def build_auto_deploy_guard_from_env() -> AutoDeployGuard:
    return AutoDeployGuard(
        min_interval_s=env_int("AUTODEPLOY_MIN_INTERVAL_S", 3600),
        max_rollout_pct=env_int("AUTODEPLOY_MAX_ROLLOUT_PCT", 10),
    )
