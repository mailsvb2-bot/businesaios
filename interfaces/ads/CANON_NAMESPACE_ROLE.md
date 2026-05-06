# interfaces/ads namespace role

- `google_ads_connector.py` and `tiktok_ads_connector.py` are the canonical public import surface.
- `*_legacy.py` modules are compatibility implementation holders and must not be imported directly outside:
  - canonical shim modules in this namespace
  - tests
- New connector logic must land behind the canonical shim surface, not in parallel modules.
