# CANON_HOTSPOT_RENAME_PLAN_V1

This document defines controlled renaming for legacy dangerous module names.

## Hotspot legacy names
- core/economics/brain.py
- core/economics/capital_engine.py
- core/economics/capital_allocation_engine.py
- core/growth/autopilot_engine.py
- runtime/handlers/ads_autopilot_flow.py

## Canonical target names
- core/economics/brain.py
  -> core/economics/economics_recommendation_service.py

- core/economics/capital_engine.py
  -> core/economics/capital_scenario_service.py

- core/economics/capital_allocation_engine.py
  -> core/economics/capital_allocation_selector.py

- core/growth/autopilot_engine.py
  -> core/growth/growth_recommendation_service.py

- runtime/handlers/ads_autopilot_flow.py
  -> runtime/handlers/ads_decision_flow_handler.py

## Migration policy
1. Do not rename all files in one pass.
2. First stabilize behavior and contracts.
3. Then rename file-by-file with import shims.
4. Delete legacy names only after all imports are migrated.
