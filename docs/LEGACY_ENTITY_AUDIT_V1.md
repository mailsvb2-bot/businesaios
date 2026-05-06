# Legacy Entity Audit V1

Legacy entity audit (phase 1).

Removed now (dead, no runtime imports):
- core/policy/safe_rollout_legacy.py
- core/finance/contracts_legacy.py

Canonicalized now (legacy kept as thin alias only):
- core/knowledge/contracts.py now hosts canonical contract protocols.
- core/knowledge/contracts_legacy.py now re-exports from canonical contracts only.
- runtime/platform/event_store/sqlite_event_store.py now hosts canonical implementation.
- runtime/platform/event_store/sqlite_event_store_legacy.py now re-exports canonical class only.
- core/economics/capital_engine.py now hosts canonical CAE implementation.
- core/economics/capital_engine_legacy.py now re-exports canonical symbols only.
- interfaces/ads/google_ads_connector.py now hosts canonical Google Ads connector implementation.
- interfaces/ads/google_ads_connector_legacy.py now re-exports canonical symbols only.
- interfaces/ads/tiktok_ads_connector.py now hosts canonical TikTok Ads connector implementation.
- interfaces/ads/tiktok_ads_connector_legacy.py now re-exports canonical symbols only.

Keep as compatibility shim (still used by canonical path):
- core/knowledge/contracts_legacy.py (legacy alias used by historical imports)
- runtime/platform/event_store/sqlite_event_store_legacy.py (legacy alias used by historical imports)
- core/economics/capital_engine_legacy.py (legacy alias used by historical imports)
- interfaces/ads/google_ads_connector_legacy.py (legacy alias used by historical imports)
- interfaces/ads/tiktok_ads_connector_legacy.py (legacy alias used by historical imports)

Migrate later (active compatibility surface):
- core/products/product_contract_compat.py
- core/llm/providers/openai_compat.py
- core/api/compat.py
- core/offers/catalogs/legacy_catalog.py
- 
Rules for next phases:
- keep business logic in canonical modules only;
- keep shim modules thin and explicit;
- delete legacy only after zero-import proof and full green regression.
