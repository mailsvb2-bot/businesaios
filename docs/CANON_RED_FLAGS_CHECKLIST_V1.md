# CANON RED FLAGS CHECKLIST V1

Цель:
не допустить появления распределённого предрешателя, второго мозга, скрытого narrowing action space и обхода единого DecisionCore.

## Разрешённые роли новых доменов

Новые домены и сервисы могут только:
- enrich
- explain
- score
- observe
- read
- write
- project
- validate
- guard

## Запрещённые скрытые роли

Новые домены и сервисы не имеют права:
- silently filter action space
- auto-select winner
- choose best business action
- inject defaults that determine outcome
- bypass DecisionCore
- issue final business decision
- pre-route final action in runtime handlers
- import legacy implementations into active flow

## Обязательный закон

DecisionCore — единственный центр final business decision.

Все остальные домены обязаны оставаться advisory / observational / constraining / explanatory и не имеют права превращаться в hidden pre-decision layer.
