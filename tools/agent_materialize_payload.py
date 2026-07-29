from __future__ import annotations
import base64
import io
import shutil
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARTS = sorted((ROOT / "tools" / "agent_materialize_parts").glob("payload_*.txt"))
DELETIONS = ('crm/public_api.py', 'runtime/world_state/public_api.py')
TEMP_PATHS = (
    ROOT / ".github" / "workflows" / "agent-materialize.yml",
    ROOT / "tools" / "agent_materialize_payload.py",
    ROOT / "tools" / "agent_materialize_parts",
)

def _safe_extract(archive: tarfile.TarFile) -> None:
    root = ROOT.resolve()
    for member in archive.getmembers():
        target = (ROOT / member.name).resolve()
        if root not in target.parents and target != root:
            raise RuntimeError(f"unsafe archive member: {member.name}")
    archive.extractall(ROOT)

def main() -> None:
    encoded = "".join(path.read_text(encoding="ascii") for path in PARTS)
    raw = base64.b85decode(encoded.encode("ascii"))
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as archive:
        _safe_extract(archive)
    for rel in DELETIONS:
        path = ROOT / rel
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()
    for path in TEMP_PATHS:
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()

if __name__ == "__main__":
    main()
