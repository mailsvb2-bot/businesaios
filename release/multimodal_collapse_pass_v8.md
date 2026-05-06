# Multimodal collapse pass v8

This pass integrates multiple ownership fixes in one sweep while preserving the existing behavioral surface:

- Collapsed 7 thin `catalog.py` package-owner surfaces into their owning package roots:
  - `demand_capture.sources`
  - `demand_product`
  - `economics`
  - `experimentation`
  - `onboarding`
  - `observability.finance`
  - `observability.demand`
- Added `shared/package_submodule_alias.py` so historical `package.catalog` imports keep working after a package-root collapse.
- Removed bespoke compat installers from `growth.platforms` and `routing_execution.channels` and replaced them with shared alias helpers.
- Kept canonical business semantics and import compatibility without introducing a second decision path.
