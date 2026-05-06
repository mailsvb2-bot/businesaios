#!/usr/bin/env bash
set -euo pipefail

# WARNING:
# Running this on a remote server can lock you out (SSH, package updates, etc.).
# Apply from an out-of-band console and add rules for your SSH + updates first.

nft add table inet filter || true
nft add chain inet filter output '{ type filter hook output priority 0; policy drop; }' || true

nft add rule inet filter output oif lo accept || true
nft add rule inet filter output ct state established,related accept || true

# DNS resolvers
nft add rule inet filter output ip daddr {1.1.1.1,8.8.8.8} udp dport 53 accept || true
nft add rule inet filter output ip daddr {1.1.1.1,8.8.8.8} tcp dport 53 accept || true

# HTTPS allowlist
nft add rule inet filter output ip daddr {203.0.113.10,203.0.113.11} tcp dport 443 accept || true
