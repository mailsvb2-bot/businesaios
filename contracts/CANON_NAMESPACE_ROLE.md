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
- future versioned `BusinessFact`, `ActionIntent`, `Execution`, `Outcome` / `Evaluation`, capability and delegated-authority contracts must extend this canonical surface instead of creating parallel semantic owners.
