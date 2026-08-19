from pathlib import Path


def test_systemd_installer_owns_mutable_tenancy_state() -> None:
    text = Path("deploy/systemd/install.sh").read_text(encoding="utf-8")

    assert 'RUNTIME_TENANCY_DIR="${RUNTIME_TENANCY_DIR:-${RUNTIME_DATA_DIR}/tenancy}"' in text
    assert 'install -d -o "$RUNTIME_USER" -g "$RUNTIME_GROUP" -m 0750 "$RUNTIME_TENANCY_DIR"' in text
    assert 'chown -R "$RUNTIME_USER:$RUNTIME_GROUP" "$RUNTIME_SECURITY_DIR" "$RUNTIME_TENANCY_DIR"' in text
    assert 'test -w "$RUNTIME_TENANCY_DIR"' in text
