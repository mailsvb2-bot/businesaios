# Decision Sovereignty

DecisionCore is the single authority for final business decisions.

Other modules may:
- score
- observe
- explain
- validate
- recommend
- guard
- enrich
- project

Other modules may NOT:
- choose final business winner
- silently narrow action space to one outcome
- issue final executable decision
- bypass RuntimeGuard / RuntimeExecutor route

## Shadow observation boundary

- Shadow runs only after DecisionCore has issued the production envelope.
- DecisionCore is the sole owner allowed to select and invoke the configured shadow candidate.
- Shadow receives a copied state and emits evidence only; it may not route, sign, issue, execute, deploy, write outbox, or change the production decision.
- Shadow candidates must come from the canonical pure `core.policies` namespace.
- Promotion remains a sealed RuntimeExecutor effect and fails closed without governed shadow evidence.


## External intelligence boundary

- Any external AI, SaaS, bot, agent, planner, or domain engine connected in a managed/delegated execution mode is subordinate intelligence, never a second business decision authority.
- Managed external execution receives an immutable sovereign `ActionIntentV2` plus execution metadata only. The original `BusinessGoalEnvelope` does not cross the managed execution boundary.
- External intelligence may optimize execution mechanics only inside the delegated intent and capability scope. It may not independently change business intent, target, capability, budget, risk, policy, approval requirement, expected outcome, or decision provenance.
- A managed external adapter that cannot execute the sovereign intent contract fails closed; it must not fall back to goal-level execution.
- External results are execution evidence/outcomes for a future DecisionCore cycle, not new executable business decisions.
- Standalone or supervised product operation may retain local intelligence, but BusinessAIOS-managed execution must use the sovereign intent boundary.
