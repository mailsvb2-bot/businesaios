import subprocess
import sys


def test_network_blocked_in_seccomp():
    code = """
import socket
socket.socket()
"""

    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
    )

    # без seccomp должно быть ОК
    assert proc.returncode == 0


def test_network_blocked_with_seccomp():
    code = """
from runtime.sandbox.seccomp_profile import apply_seccomp
apply_seccomp()

import socket
socket.socket()
"""

    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
    )

    assert proc.returncode != 0
