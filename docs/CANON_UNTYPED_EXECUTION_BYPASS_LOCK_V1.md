# CANON_UNTYPED_EXECUTION_BYPASS_LOCK_V1

This canon lock protects the system from an untyped execution bypass.

## Main risk

A second brain often returns not through explicit `DecisionCommand`,
but through untyped bridges such as:

- dict
- payload
- envelope
- response
- result
- proposal object
- generic service output

That data is then used downstream to reconstruct action authority
without passing through DecisionCore.

## Forbidden pattern

The following path is forbidden:

RecommendationSet
-> dict / payload / envelope / result
-> handler / helper / service
-> execute / apply / launch / mutate

## Allowed path

The only allowed bridge is:

RecommendationSet
-> DecisionCore
-> DecisionCommand
-> execution boundary
-> execution service / connector

## Canon execution-boundary rule

Execution boundary functions must:

- accept explicit `DecisionCommand`
- validate explicit `DecisionCommand`
- pass explicit `DecisionCommand` to execution service

Execution boundary functions must not:

- accept payload-like alternatives
- rebuild command fields from dicts
- rebuild command fields from generic objects
- construct inline command from recommendation payload

## Why teams miss this

Many teams protect type-level decision emission,
but forget that untyped transport objects can reintroduce decision authority.
That creates a hidden second brain without breaking obvious type-based locks.
