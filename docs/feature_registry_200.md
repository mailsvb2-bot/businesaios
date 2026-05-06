# Feature Registry 200

`core/marketing/feature_registry_200.py` defines a stable list of 200 features.

## Why

- A single canonical vocabulary prevents extractors from guessing names.
- Makes training / dashboards / retention stable across products.
- Works with Dirac Behavioral OS outputs + telemetry.

## How to use

- Extract raw facts from event_store (telemetry).
- Compute daily aggregates into `user_features_daily`.
- Map aggregates into this registry (name -> value).

DecisionCore / retention engines can safely read these features, but must still
respect policy gate + soft backoff constraints.
