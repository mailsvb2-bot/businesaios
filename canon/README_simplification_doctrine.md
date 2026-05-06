# Canon Simplification Doctrine

## Purpose

This doctrine defines ideal simplification for the project.

A valid simplification must preserve:
- meanings
- full functionality
- decision discipline
- safety logic
- observability
- true domain boundaries

A valid simplification may remove only:
- duplicate paths
- parasitic glue logic
- synonymous logic
- false fallback truth
- duplicate guard logic

## Non-negotiable target shape

Every valid simplification should converge toward:
- one layer with real logic
- one thin boundary adapter

## Forbidden regressions

A simplification is invalid if it causes any of the following:
- more than one decision path
- bypass of DecisionCore
- weaker route discipline
- weaker guarded execution
- loss of stop-loss, policy gates, or fail-closed behavior
- weaker tenant hard gates
- loss of schema validation
- loss of trace ids, correlation ids, snapshots, event history, or decision archive
- domain soup between retention, offers, messaging policy, ads autopilot, and behavior logic
- silent public contract breakage

## Operating protocol

Before any radical simplification, every candidate layer must be classified as exactly one of:
- KEEP
- MERGE
- DELETE

No simplification is valid without:
- explicit proposal
- invariant check
- regression tests
- proof of full functionality preservation
- proof that no hidden second path is opened
- proof that separate architectural locks remain distinct and readable

## Anti-self-deception rule

A change is not an improvement merely because it reduces file count, line count, or abstraction count.
If it weakens safety, observability, route discipline, or architectural boundaries, it is forbidden.


## Architectural lock preservation

Reduce only what does not blur separate architectural locks.
Do not merge independent canonical-path, decision, finance, safety, or transition locks into one mega-lock if that weakens signal localization, hides an alternative path, or makes the failing constraint ambiguous.
