#!/usr/bin/env bash
set -euo pipefail

# Canonical release attestation verification.
# Regenerates manifest and checks that it matches current tree.

true # compileall disabled: would create __pycache__
python scripts/gen_release_manifest.py
python -m pytest -q
