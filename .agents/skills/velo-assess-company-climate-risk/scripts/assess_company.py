#!/usr/bin/env python3
"""Export a read-only VELO company or market-index diligence bundle."""

from __future__ import annotations

import argparse
import json
from importlib.metadata import version
from pathlib import Path

from velo_sdk.api import APIClient


def records(iterator: object) -> list[dict]:
    return [item.model_dump(mode="json") for item in iterator]  # type: ignore[union-attr]


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    target = p.add_mutually_exclusive_group(required=True)
    target.add_argument("--company-id")
    target.add_argument("--index-id")
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

    if args.company_id:
        target_type = "company"
        target = client.companies.get_company(args.company_id)
        total = client.companies.get_company_climate_scores(target.id, args.pathway, args.horizon)
        factor_impacts = records(client.companies.get_company_impact_scores(target.id, args.pathway, args.horizon))
        country_concentration = records(client.companies.aggregate_company_asset_climate_scores_by_country(target.id, args.pathway, args.horizon))
        asset_type_concentration = records(client.companies.aggregate_company_asset_climate_scores_by_asset_type(target.id, args.pathway, args.horizon))
    else:
        target_type = "market_index"
        target = client.markets.get_index(args.index_id)
        total = client.markets.get_index_climate_scores(target.id, args.pathway, args.horizon)
        factor_impacts = records(client.markets.get_index_impact_scores(target.id, args.pathway, args.horizon))
        country_concentration = records(client.markets.aggregate_index_asset_climate_scores_by_country(target.id, args.pathway, args.horizon))
        asset_type_concentration = records(client.markets.aggregate_index_asset_climate_scores_by_asset_type(target.id, args.pathway, args.horizon))

    result = {
        "sdk_version": version("velo-sdk"),
        "target_type": target_type,
        "target": target.model_dump(mode="json"),
        "pathway": args.pathway,
        "horizon": args.horizon,
        "climate_score": total.model_dump(mode="json"),
        "factor_impacts": factor_impacts,
        "country_concentration": country_concentration,
        "asset_type_concentration": asset_type_concentration,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
