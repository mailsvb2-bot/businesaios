#!/usr/bin/env bash
set -euo pipefail

# Minimal CI hook for running TLC if available in PATH.
# If TLC isn't installed, exit non‑zero to fail safe.
command -v tlc >/dev/null 2>&1 || { echo "TLC (tlc) not available"; exit 2; }

tlc formal/decision_core.tla
tlc formal/governance.tla
tlc formal/rl_economy.tla
