# Canon: Second-Brain Lock Rules

## Core invariant

Only `DecisionCore` may issue decision-routed actions.

## Forbidden

The following are forbidden outside `DecisionCore`:

- direct action issuance
- direct policy mutation
- direct apply-path invocation
- strategy changes derived inside reward/evaluation layers
- growth/autopilot direct execution without DecisionCore-issued envelope

## Allowed

Other layers may:

- enrich state
- score candidates
- evaluate outcomes
- prepare proposals
- queue proposals via gateway
- execute already-issued action envelopes

## Decision route

Critical runtime handlers must require:

- `decision_id`
- `correlation_id`
- `issuer_id == "businesaios-core"`
- expected action type
- explicit route metadata

## Layer contracts

- `core/reward/*` -> observe only
- `core/pricing/rl/*` -> score/select only
- `core/growth/*` -> propose/queue only
- `runtime/handlers/*` -> execute only
- `core/ai/*` -> only canonical issue path

<!-- CANON_DOMAIN_SECOND_BRAIN_EXTENSION_V1:START -->
## Extension: strategic domains are enrichment-only, not issuers

The following domains, when introduced canonically, are enrichment / constrain / audit / simulation domains:

- world_model
- economics
- experiments
- knowledge
- product
- governance
- finance
- simulation
- learning_loop
- human_governance

They may:

- read
- build state
- evaluate
- explain
- guard
- project
- write audit records
- propose constrained updates

They may not:

- issue DecisionRoute directly
- call direct apply handlers
- choose final business actions
- mutate strategy outside canonical decision flow
- act as parallel CEO
<!-- CANON_DOMAIN_SECOND_BRAIN_EXTENSION_V1:END -->
