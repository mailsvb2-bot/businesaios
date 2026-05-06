# Canon Runtime Thin Handlers V1

Runtime handlers are execution shells, not brains.

A runtime handler marked:

`CANON_THIN_HANDLER = True`

must only:

- parse input
- call thin services / builders / guards
- pass canonical envelopes
- return response

It must not:

- decide strategy
- choose actions
- mutate policy
- issue DecisionRoute
- become an alternative decision center
