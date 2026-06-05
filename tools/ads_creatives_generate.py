from __future__ import annotations

import argparse
import json

from core.growth.ads.creative import generate_candidates, select_creative
from interfaces.llm import TemplatedLLM


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate ad creative candidates (text-only).")
    ap.add_argument("--offer-arm", required=True)
    ap.add_argument("--business-type", required=True)
    ap.add_argument("--offer-title", required=True)
    ap.add_argument("--offer-details", required=True)
    ap.add_argument("--city", default="")
    ap.add_argument("--n", type=int, default=3)
    args = ap.parse_args()

    llm = TemplatedLLM()
    cands = generate_candidates(
        offer_arm=args.offer_arm,
        business_type=args.business_type,
        offer_title=args.offer_title,
        offer_details=args.offer_details,
        city=args.city,
        llm=llm,
        n=args.n,
    )
    sel = select_creative(candidates=cands)
    print(
        json.dumps(
            {
                "selected": {
                    "creative_id": sel.selected.creative_id,
                    "headline": sel.selected.headline,
                    "primary_text": sel.selected.primary_text,
                    "description": sel.selected.description,
                    "cta": sel.selected.cta,
                },
                "scores": sel.scores,
                "reason": sel.reason,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
