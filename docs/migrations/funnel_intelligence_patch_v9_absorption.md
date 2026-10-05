# Funnel Intelligence v9 — canonical absorption record

Source reviewed: `BusinessAIOS_Funnel_Intelligence_Patches_v9_FAIL_CLOSED_CONVERSATIONAL_RUNTIME`.

## Decision

The patch pack is useful, but it must **not** be applied wholesale. BusinessAIOS already owns the canonical DecisionCore, ActionIntent, DurableTask, Memory v2, Experiment Engine, Attribution Engine, provider queue/outbound runtime and conversation registry. The donor pack contains modules named `decision`, `decision_policy`, `repositories`, `message_memory`, `sequence_orchestrator`, `outbound_lifecycle`, `experiments`, `attribution`, `revenue` and `live_orchestrator`; importing them as independent owners would create parallel authority.

## Absorbed in this slice

Only deterministic, side-effect-free evidence/constraint logic is absorbed:

- numeric provider source ordering (`10 > 9`, `010 == 10`);
- tenant/channel/subject/provider-event scoped inbound dedupe assessment;
- stale inbound evidence rejection;
- derived conversation-stage projection where checkout request is not checkout creation;
- hard payment/decline stage evidence;
- verified offer revision / verified price checks;
- follow-up suppressors, daily/weekly/sequence caps, minimum gaps and quiet-hours constraints;
- conversation signal, fatigue and pressure calculations.

The new package is under `advisory/funnel_intelligence`. It returns evidence and constraints only. It cannot send, enqueue, schedule, persist, authorize an ActionIntent, issue a decision, own memory, own attribution, or create a durable task.

## Intentionally not absorbed as owners

The following donor concepts remain unmerged as independent runtime components:

- next-best-action / decision selection;
- donor DecisionPolicy / live dispatch authority;
- donor repository protocols and in-memory repository implementations;
- donor message memory;
- donor sequence scheduler/orchestrator;
- donor outbound lifecycle;
- donor experiment/bandit authority;
- donor attribution/revenue ownership;
- donor provider dispatch;
- donor handoff persistence.

Future Phase 18 work may reuse their **behavioral rules** only by mapping them into the corresponding canonical BusinessAIOS owner.

## No-second-brain gate

`tests/arch/test_funnel_intelligence_no_second_brain.py` prevents the advisory package from importing canonical runtime owners or growing repository/router/scheduler/outbox/memory/engine classes and blocks obvious storage/network/process side effects.
