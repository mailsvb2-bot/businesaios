from __future__ import annotations

CANON_BOOT_ADS_WIRING_RUNTIME_OWNER = True
CANON_BOOT_WIRING_ONLY = True

from bootstrap.ads_wiring import build_ads_runtime, build_ads_service
from bootstrap.ads_wiring import AdsRuntime as _BootstrapAdsRuntime


class AdsRuntime(_BootstrapAdsRuntime):
    pass


__all__ = ["AdsRuntime", "build_ads_runtime", "build_ads_service"]
