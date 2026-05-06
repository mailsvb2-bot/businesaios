SUSPECT_KEYS = ["SECRET", "TOKEN", "KEY", "PASSWORD"]


def _is_suspect(key: object) -> bool:
    ku = str(key).upper()
    return any(s in ku for s in SUSPECT_KEYS)


def assert_no_secrets(payload: dict) -> None:
    """Hard guard: secrets must never enter Decision Ring artifacts.

    Raises RuntimeError if any key in the payload tree looks like it may
    contain secrets.

    Intended call sites:
      - before DecisionCore.optimize()
      - before DecisionLedger append/write
      - before ML dataset write
    """

    def walk(obj: object) -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                if _is_suspect(k):
                    raise RuntimeError("Secret leak into Decision Ring")
                walk(v)
        elif isinstance(obj, (list, tuple)):
            for it in obj:
                walk(it)

    walk(payload)