# CANON_RECOMMENDATION_EXECUTION_BRIDGE_V1

This canon document protects the project from a hidden second brain.

## Main rule

Recommendation-stage modules may:

- read
- build
- evaluate
- explain
- constrain
- propose

Recommendation-stage modules may not:

- execute
- dispatch
- launch
- apply
- mutate
- call execution services directly
- call connectors directly
- return execution objects

## Allowed bridge

The only allowed bridge from recommendation stage to execution stage is:

RecommendationSet
-> DecisionCore
-> DecisionCommand
-> execution boundary
-> execution service / connector

## Forbidden bridge

The following route is forbidden:

RecommendationSet
-> handler / helper / gateway / client
-> execute / apply / launch / mutate

## Hidden regression that teams often miss

Many teams ban direct `DecisionCommand` creation,
but still allow recommendation modules to:

- hold execution dependencies
- import helper modules with hidden side effects
- call launch/apply/execute verbs indirectly

That recreates a second brain without using `DecisionCommand` explicitly.
