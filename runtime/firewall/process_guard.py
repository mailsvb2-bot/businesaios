import threading

_process_local = threading.local()

class ProcessCapabilityError(RuntimeError):
    pass

def set_effect_capability(token: str):
    _process_local.effect_token = token

def clear_effect_capability():
    _process_local.effect_token = None

def require_effect_capability(expected: str):
    token = getattr(_process_local, "effect_token", None)
    if token != expected:
        raise ProcessCapabilityError(
            "[FIREWALL] Missing or invalid process capability token"
        )
