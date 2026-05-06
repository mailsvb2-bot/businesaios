# GitHub Publication Status — BusinesAIOS

## Allowed publication label

Publish this repository as:

- platform kernel
- alpha / beta
- experimental runtime
- pre-production foundation

## Forbidden claim before P0 closure

Do **not** publish or market this repository as:

- production ready autonomous business OS
- fully production-ready business autopilot
- completed autonomous business engine

## Publication contract

Before push/publication:

- CI gates must be green
- `.gitignore` must exclude runtime state, logs, local env files, archives, and databases
- no committed runtime artifacts or local data files
- no committed secrets or hard-coded credentials
- no broken GitHub workflows
- root entry contract must be explicit in `README.md`
- maturity must be described honestly
