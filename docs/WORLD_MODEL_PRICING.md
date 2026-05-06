# Pricing World Model (Demand Curves + Elasticity + Conversion Dynamics)

This document describes the **pure** (side‑effect free) world model primitives used to derive
features for pricing decisions (DecisionCore remains the only brain).

## What it covers

- Demand curves: isoelastic / linear / piecewise linear
- Elasticity: point & arc elasticity helpers
- Conversion dynamics: logistic conversion vs price; funnel transitions (visit → cart → checkout → purchase)
- Seasonality: day‑of‑week multipliers (extendable)

## Architecture rules (canonical)

- `core/economics/world_model/*` is **PURE**: no DB/network imports, no writes.
- Parameter **storage** is platform‑layer (`runtime/platform/economics/world_model_store.py`).
- Offline training is in `ml/world_model_trainer.py` (no external deps).

## Training loop (offline)

1. Build aggregated observations per tenant/product:
   - `DemandObservation(price, units, context)`
   - `ConversionObservation(price, conversions, opportunities, context)`
2. Train:
   - `train_pricing_world_model(...)`
3. Serialize:
   - `export_pricing_world_model_payload(model)`
4. Store:
   - `WORLD_MODEL_DIR/<tenant>/<product>/<model_id>.json`
   - `WORLD_MODEL_DIR/<tenant>/<product>/ACTIVE` contains the active `model_id`

## Runtime usage (pure)

```python
from core.economics.world_model.world_model import PricingWorldModel
from core.economics.world_model.types import MarketContext
from core.economics.world_model.world_state import WorldModelInput

wm = PricingWorldModel.default()
ws = wm.build(WorldModelInput(context=MarketContext(tenant_id="t", product_id="p"), current_price=20.0))
print(ws.point_elasticity, ws.expected_profit)
```

## Guardrails

- Models clamp probabilities away from 0/1.
- Fits are dependency‑free and defensive; low data falls back to defaults.
- A lock‑test prevents `core.economics.world_model` from importing platform code.
