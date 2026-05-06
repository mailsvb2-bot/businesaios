# Cilium egress policies (FQDN + optional L7 HTTP)

Contains:
- `egress-fqdn-only.yaml`: allow DNS + HTTPS only to specific domains
- `egress-http-l7.yaml`: optional HTTP L7 allow-list (methods/paths)

Requires Cilium CNI with FQDN and L7 policy support.
