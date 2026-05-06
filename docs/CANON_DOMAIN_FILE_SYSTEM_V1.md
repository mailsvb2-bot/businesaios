# Canon Domain File System V1

This canon applies to new strategic domains that explicitly opt in via:

`core/<domain>/__canon_domain__.py`

with:

`CANON_DOMAIN_VERSION = "DFS-V1"`

## Strategic domains

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

## Required root files

Every canon strategic domain must contain:

- contracts.py
- types.py
- errors.py
- service.py
- guard.py

Optional root files:

- __init__.py
- __canon_domain__.py
- enums.py
- ids.py
- policy.py

No other python files are allowed in the domain root.

## Allowed role folders

- readers
- writers
- builders
- evaluators
- explainers
- guards
- policies
- repositories
- projections
- serializers
- mappers
- events

## Forbidden fuzzy roles

Forbidden names in new strategic domains:

- brain
- engine
- manager
- orchestrator
- commander
- director
- master
- supervisor
- processor

## Role semantics

- reader -> read only
- writer -> write only
- builder -> compose structures only
- evaluator -> evaluate only
- explainer -> explain only
- guard -> validate/block only
- policy -> return policy result only
- service -> thin orchestration facade only
- repository -> persistence abstraction only
- projection -> read model materialization only
- serializer -> serialization only
- mapper -> transformation only
- events -> event payloads/contracts only

## Second-brain prohibition

Strategic domains may enrich, constrain, explain, simulate, audit, and project.

Strategic domains may not:

- issue final decisions
- build DecisionRoute directly
- call apply-path handlers directly
- bypass DecisionCore
- become an alternative CEO

Allowed path:

`read -> analyze -> propose / constrain / explain -> DecisionCore`
