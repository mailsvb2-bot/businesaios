"""Event-sourced business flows ported into DecisionCore actions.

Every flow here is a PURE projection over canonical Event Store facts plus a
pure transition function. No flow owns a store, a scheduler or a decision:
DecisionCore proposes the action, the executor runs it, and the handler
records the resulting transition as a tracked event of the delivered reply.
"""
