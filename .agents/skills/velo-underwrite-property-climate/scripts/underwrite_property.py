#!/usr/bin/env python3
"""Read a VELO asset's climate and factor-impact evidence without mutation."""

from __future__ import annotations

import argparse
import json
from importlib.metadata import version
from itertools import islice
from pathlib import Path
from typing import Any

from velo_sdk.api import APIClient


def dump(value: Any) -> Any:
    return value.model_dump(mode="json") if hasattr(value, "model_dump") else value


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    identity = p.add_mutually_exclusive_group(required=True)
    identity.add_argument("--asset-id")
    identity.add_argument("--query")
    p.add_argument("--pathway", required=True)
    p.add_argument("--horizon", required=True, type=int)
    p.add_argument("--output", required=True, type=Path)
    return p


def main() -> int:
    args = parser().parse_args()
    client = APIClient()
    pathways = [str(item) for item in client.climate.list_pathways()]
    horizons = client.climate.list_horizons()
    if args.pathway not in pathways or args.horizon not in horizons:
        raise SystemExit(f"unsupported scenario; pathways={pathways}, horizons={horizons}")

    if args.asset_id:
        asset = client.assets.get_asset(args.asset_id)
    else:
        candidates = list(islice(client.assets.search_assets(args.query), 11))
        if len(candidates) != 1:
            visible_candidates = candidates[:10]
            truncated = len(candidates) > len(visible_candidates)
            print(
                json.dumps(
                    {
                        "status": "selection_required",
                        "query": args.query,
                        "returned_count": len(visible_candidates),
                        "match_count": None if truncated else len(candidates),
                        "match_count_lower_bound": len(candidates),
                        "truncated": truncated,
                        "message": (
                            "Showing the first 10 matches; refine the query before selecting an asset."
                            if truncated
                            else (
                                "Select one of the returned matches."
                                if candidates
                                else "No matching assets found; revise the query."
                            )
                        ),
                        "candidates": [dump(item) for item in visible_candidates],
                    },
                    indent=2,
                )
            )
            return 2
        asset = candidates[0]

    owner = client.assets.get_asset_owner(asset.id)
    score = next((item for item in client.companies.list_company_asset_climate_scores(owner.id, args.pathway, args.horizon) if item.asset_id == asset.id), None)
    impacts = next((item for item in client.companies.list_company_asset_impact_scores(owner.id, args.pathway, args.horizon) if item.asset_id == asset.id), None)
    result = {
        "sdk_version": version("velo-sdk"),
        "pathway": args.pathway,
        "horizon": args.horizon,
        "asset": dump(asset),
        "owner": dump(owner),
        "climate_score": dump(score),
        "impact_scores": dump(impacts),
        "warnings": [] if score is not None else ["No matching asset climate score returned; this is not evidence of low risk."],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
