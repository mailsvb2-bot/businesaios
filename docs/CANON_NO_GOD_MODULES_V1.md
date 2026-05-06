# Canon No God Modules V1

No new architecture may introduce god modules or god services.

## Root line limits for canon strategic domains

- service.py <= 220 lines
- policy.py <= 180 lines
- guard.py <= 180 lines
- contracts.py <= 220 lines
- types.py <= 220 lines
- errors.py <= 140 lines
- enums.py <= 160 lines
- ids.py <= 160 lines

If logic exceeds the limit, it must be moved into dedicated role folders.

## Runtime thin-handler limit

Runtime handlers marked with:

`CANON_THIN_HANDLER = True`

must stay <= 180 lines and must not define decision logic.

## Boot wiring-only limit

Boot modules marked with:

`CANON_BOOT_WIRING_ONLY = True`

must stay <= 180 lines and must not contain:

- direct business logic
- network side effects
- subprocess usage
- direct execution
- decision logic
