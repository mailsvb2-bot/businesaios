from __future__ import annotations

import logging

from learning.rollout import RolloutGuard
from runtime.ads import AdsRLOptimizerDeps, AdsRLOptimizerService
from runtime.boot.failure_policy import raise_or_log_boot_failure
from runtime.platform.config.env_flags import env_bool

CANON_BOOT_WIRING_ONLY = True



LOGGER = logging.getLogger(__name__)


def build_ads_rl_service(*, ads_service, event_store, logger=None) -> AdsRLOptimizerService | None:
    """Optional Ads RL optimizer wiring.

    Enabled by env:
      ADS_RL_ENABLED=1

    Dependencies:
      - AdsService (read metrics, optionally apply plans via other actions)
      - event_store (experience)
      - RolloutGuard (extra safety)
    """

    if not env_bool("ADS_RL_ENABLED"):
        return None

    try:
        svc = AdsRLOptimizerService(
            AdsRLOptimizerDeps(
                ads=ads_service,
                event_store=event_store,
                rollout_guard=RolloutGuard(),
            )
        )
    except Exception as exc:
        raise_or_log_boot_failure(
            component="ads_rl",
            exc=exc,
            logger=logger or LOGGER,
        )
        return None

    if logger is not None:
        logger.info("ADS_RL enabled")
    return svc
