from __future__ import annotations

import argparse
import json

from application.governance.governance_service import GovernanceService

CANON_HEADLESS_GOVERNANCE_ADVANCED_CLI = True

def _parser() -> argparse.ArgumentParser:
    parser=argparse.ArgumentParser(prog='businesaios-governance-advanced'); sub=parser.add_subparsers(dest='command', required=True)
    rr=sub.add_parser('rollback-recommendation'); rr.add_argument('--baseline-name', required=True); rr.add_argument('--candidate-run-id', required=True); rr.add_argument('--fallback-run-id', action='append', required=True)
    jh=sub.add_parser('joined-history'); jh.add_argument('--baseline-name', required=True); jh.add_argument('--candidate-run-id', action='append', required=True)
    ve=sub.add_parser('verify-evidence'); ve.add_argument('--baseline-name', required=True)
    ps=sub.add_parser('promote-scenario'); ps.add_argument('--scenario', required=True); ps.add_argument('--run-id', action='append', required=True); ps.add_argument('--suffix', default='golden'); ps.add_argument('--label', default='scenario_auto')
    tl=sub.add_parser('timeline'); tl.add_argument('--baseline-name', required=True)
    dt=sub.add_parser('trend'); dt.add_argument('--baseline-name', required=True); dt.add_argument('--candidate-run-id', action='append', required=True)
    ms=sub.add_parser('memory-summary'); ms.add_argument('--tenant-id', required=True); ms.add_argument('--business-id', required=True)
    return parser

def main(argv: list[str] | None = None) -> int:
    args=_parser().parse_args(argv); governance=GovernanceService.build_default()
    if args.command=='rollback-recommendation': print(json.dumps(governance.rollback_recommendation(baseline_name=args.baseline_name, candidate_run_id=args.candidate_run_id, fallback_run_ids=args.fallback_run_id), ensure_ascii=False, indent=2, sort_keys=True)); return 0
    if args.command=='joined-history': print(json.dumps(governance.joined_history(baseline_name=args.baseline_name, candidate_run_ids=args.candidate_run_id), ensure_ascii=False, indent=2, sort_keys=True)); return 0
    if args.command=='verify-evidence': print(json.dumps(governance.verify_promotion_evidence(baseline_name=args.baseline_name), ensure_ascii=False, indent=2, sort_keys=True)); return 0
    if args.command=='promote-scenario': payload=governance.promote_best_for_scenario(scenario=args.scenario, run_ids=list(args.run_id), suffix=args.suffix, label=args.label, metadata={'via':'cli'}); print(json.dumps(payload or {}, ensure_ascii=False, indent=2, sort_keys=True)); return 0 if payload else 1
    if args.command=='timeline': print(governance.rollback_timeline(baseline_name=args.baseline_name)); return 0
    if args.command=='trend': print(json.dumps(governance.drift_trend(baseline_name=args.baseline_name, candidate_run_ids=list(args.candidate_run_id)), ensure_ascii=False, indent=2, sort_keys=True)); return 0
    if args.command=='memory-summary': print(json.dumps(governance.memory_summary(tenant_id=args.tenant_id, business_id=args.business_id), ensure_ascii=False, indent=2, sort_keys=True)); return 0
    return 2
if __name__ == '__main__': raise SystemExit(main())
