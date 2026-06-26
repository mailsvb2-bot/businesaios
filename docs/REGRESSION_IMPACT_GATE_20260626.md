# Regression impact gate — 2026-06-26

BusinessAIOS needs a regression contour that maps changed repository paths to the regression checks that must be present in the CI plan.

The first implementation is intentionally bounded:

- no DecisionCore changes;
- no runtime execution changes;
- no workflow edits;
- no generated artifact churn;
- CI-only impact policy and tests.

This gate prevents silent drift by making dangerous path families explicit: CI, runtime, storage, billing, tenancy, security, interfaces, workflows, and generated/runtime artifacts.
