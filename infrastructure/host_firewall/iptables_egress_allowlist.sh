#!/usr/bin/env bash
set -euo pipefail

# WARNING:
# Running this on a remote server can lock you out (SSH, package updates, etc.).
# Apply from an out-of-band console and add rules for your SSH + updates first.

# default deny outbound
iptables -P OUTPUT DROP

# allow loopback
iptables -A OUTPUT -o lo -j ACCEPT

# allow established/related
iptables -A OUTPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT

# allow DNS to resolvers (example: 1.1.1.1 and 8.8.8.8)
iptables -A OUTPUT -p udp -d 1.1.1.1 --dport 53 -j ACCEPT
iptables -A OUTPUT -p udp -d 8.8.8.8 --dport 53 -j ACCEPT
iptables -A OUTPUT -p tcp -d 1.1.1.1 --dport 53 -j ACCEPT
iptables -A OUTPUT -p tcp -d 8.8.8.8 --dport 53 -j ACCEPT

# allow HTTPS only to specific IPs (example)
iptables -A OUTPUT -p tcp -d 203.0.113.10 --dport 443 -j ACCEPT
iptables -A OUTPUT -p tcp -d 203.0.113.11 --dport 443 -j ACCEPT

# NOTE: add SSH allow rules before enabling DROP if you need remote access.
