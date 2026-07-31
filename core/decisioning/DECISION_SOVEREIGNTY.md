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
