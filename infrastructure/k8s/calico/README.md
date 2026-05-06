# Calico GlobalNetworkPolicy examples

Contains:
- `global-default-deny-egress.yaml`: deny all egress cluster-wide
- `global-allow-egress-dns-and-https.yaml`: allow DNS + HTTPS to allowlisted IPs for selector `app == "runtime"`

Requires Calico CNI and cluster admin privileges for GlobalNetworkPolicy.
