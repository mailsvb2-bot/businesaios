from __future__ import annotations

from bootstrap.ads_wiring import AdsRuntime as _BootstrapAdsRuntime
from bootstrap.ads_wiring import build_ads_runtime, build_ads_service

CANON_BOOT_ADS_WIRING_RUNTIME_OWNER = True
CANON_BOOT_WIRING_ONLY = True

class AdsRuntime(_BootstrapAdsRuntime):
    pass


__all__ = ["AdsRuntime", "build_ads_runtime", "build_ads_service"]
