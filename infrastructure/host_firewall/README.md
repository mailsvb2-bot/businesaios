# Host-level egress allowlist (iptables / nftables)

These scripts implement a **default-deny OUTPUT** policy and then allow:
- loopback
- established/related
- DNS to specific resolvers
- HTTPS only to specific IPs (example placeholders)

## Safety warning
Applying a default-deny policy on a remote server can lock you out (SSH) and break updates.
Use an out-of-band console and add explicit allow rules for SSH and required infra before enabling DROP.

## Customize
Replace example IPs (203.0.113.10/11) with real provider IPs, and replace DNS resolvers if needed.
