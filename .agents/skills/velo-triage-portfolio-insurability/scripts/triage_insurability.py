#!/usr/bin/env python3
"""Export VELO platform insurability and stranding classifications for a company."""

from __future__ import annotations

import argparse
import json
from importlib.metadata import version
from pathlib import Path

from velo_sdk.api import APIClient


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--company-id", required=True)
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

    company = client.companies.get_company(args.company_id)
    uninsurable = [item.model_dump(mode="json") for item in client.companies.list_uninsurable_company_assets(company.id, args.pathway, args.horizon)]
    stranded = [item.model_dump(mode="json") for item in client.companies.list_stranded_company_assets(company.id, args.pathway, args.horizon)]
    stranded_ids = {item["asset_id"] for item in stranded}
    result = {
        "sdk_version": version("velo-sdk"),
        "company": company.model_dump(mode="json"),
        "pathway": args.pathway,
        "horizon": args.horizon,
        "definitions": {"uninsurable": "VELO cvar_95 >= 0.35", "stranded": "VELO cvar_95 >= 0.75"},
        "counts": {"uninsurable": len(uninsurable), "stranded": len(stranded), "overlap": sum(item["asset_id"] in stranded_ids for item in uninsurable)},
        "uninsurable_assets": uninsurable,
        "stranded_assets": stranded,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

