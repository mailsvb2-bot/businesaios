# contracts namespace role

This package is the **canonical domain contract surface**.

Allowed here:
- shared DTO-like contract objects
- domain-facing payload definitions
- decision, growth, supply, demand, and marketplace contracts
- stable cross-layer data shapes that core and platform layers may depend on

Must NOT contain:
- connector adapters
- HTTP/web request handlers
- provider-specific integration code
- serialization-only schema glue
- a second runtime adapter surface beside `interfaces/`

Rule:
- `contracts/` owns the **semantic contract truth**.
- `schemas/` owns **validation and serialization helpers around those truths**.
- `interfaces/` owns **boundary adapters, connectors, and delivery surfaces**.
- sovereign `Decision` / signed `DecisionEnvelope` definitions are owned by `contracts/decisioning/sovereign_decision_contract.py`; `core/ai/decision_contracts.py` is compatibility-only and must not redefine them.
- `DecisionContextProjection` is advisory input only; the sovereign world state remains `kernel.world_state.WorldStateV1`.
- `BusinessFactV1`, `ActionIntentV1`, `PolicyDecisionV1`, and `BusinessOutcomeV1` are canonical semantic contracts; application/runtime layers may project or consume them but must not redefine them.
- Future versioned `Execution`, `Evaluation`, capability and delegated-authority contracts extend this surface instead of creating parallel semantic owners.
