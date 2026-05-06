# Canon Boot Orchestration V1

Boot modules marked:

`CANON_BOOT_WIRING_ONLY = True`

are allowed to do only:

- assemble dependencies
- attach route groups
- register bundles
- connect small boot units

They are not allowed to do:

- domain business logic
- network side effects
- subprocess orchestration
- direct execution
- hidden fallback pipelines
- mixed framework logic in one place
