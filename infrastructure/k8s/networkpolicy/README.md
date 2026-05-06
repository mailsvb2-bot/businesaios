# Kubernetes egress policies (standard NetworkPolicy)

This folder contains:
- `default-deny-egress.yaml`: deny all egress in namespace `businesaios`
- `allow-dns-egress.yaml`: allow DNS to CoreDNS (kube-system / kube-dns labels)
- `allow-egress-yookassa.yaml`: allow HTTPS (443) only to allowlisted IPs for pods labeled `app=runtime`

## Notes
- Standard NetworkPolicy cannot filter by FQDN. For domain-based allowlisting, use Cilium (see `../cilium`).
- Adjust CoreDNS labels/selectors if your cluster differs.
- Replace example IPs with real provider IPs.
