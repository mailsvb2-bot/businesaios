
import hashlib
import json


def canonical_json_bytes(data: dict) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":")).encode()

def sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def payload_hash(payload: dict) -> str:
    return sha256_hex(canonical_json_bytes(payload))
