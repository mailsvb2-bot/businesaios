# CI lazy step registry precheck — 2026-06-26

Observed server failure:

- `python -m pytest ...` failed because the server environment had no `pytest` installed.
- `python -m scripts.ci.cli --gate fast` failed before producing a CI report because importing `scripts.ci.step_registry` eagerly imported `scripts.ci.step_boot_smoke`, which imports `fastapi.testclient`.

This is not an acceptable CI failure shape. The CI CLI must be able to start, build the plan, and execute the dependency-lock/preflight step before optional step modules import heavy dependencies.

Canonical rule:

- Step registry metadata must be dependency-light.
- Step handlers must be imported lazily only when the step is executed.
- Missing optional/test dependencies should be reported by the relevant step or dependency-lock gate, not crash CLI import.

Extraction rule:

- Fix registry loading without changing gate order.
- Do not alter DecisionCore.
- Do not alter runtime execution.
- Do not edit workflows.
