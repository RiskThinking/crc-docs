"""Headless portfolio risk metrics — the notebook's scaled-up twin.

Run with:

    uv run python pipelines/portfolio_risk_pipeline.py

Reconstructs per-asset hurdle distributions from the checked-in canonical
OS-Climate fixture, turns them into impact microscores via ``crc_framework``,
and aggregates portfolio VaR / CVaR with factor attribution. This is the
bridge from crc-sdk's hazard surface to crc-framework's risk metrics.
"""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from crc_framework import (
    PiecewiseLinearImpact,
    ScenarioMetadata,
    compute_risk,
    generate_microscores,
)
from crc_sdk.connectors import read_hazard_dataset, read_hazard_metadata
from crc_sdk.connectors.duckdb import DuckDBConnection, sql_quote
from crc_sdk.workflows import distribution_from_hazard_row

HAZARD_NAME = "RiverineInundation"
PATHWAY = "historical"
HORIZON = 1980

DEPTH_DAMAGE = PiecewiseLinearImpact(
    exposure=[0.0, 0.1, 0.5, 1.0, 2.0, 4.0],
    impact=[0.0, 0.01, 0.08, 0.22, 0.55, 1.0],
)
MICROSCORE_PROBABILITIES = (0.5, 0.8, 0.9, 0.95, 0.99, 0.999)
RISK_LEVELS = (0.5, 0.95, 0.99)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--hazard-input",
        type=Path,
        default=Path("fixtures/os_climate/hazard.parquet"),
    )
    parser.add_argument(
        "--asset-input",
        type=Path,
        default=Path("fixtures/os_climate/assets.parquet"),
    )
    parser.add_argument(
        "--design-probability",
        type=float,
        default=0.99,
        help="Non-exceedance probability used to form each asset BinaryOutcome "
        "(default: %(default)s → 100-year)",
    )
    parser.add_argument("--output-dir", type=Path, default=Path("pipeline_output"))
    return parser.parse_args()


def match_assets_to_hazard(
    assets_path: Path,
    hazard_path: Path,
    *,
    h3_resolution: int,
    work_dir: Path,
) -> pa.Table:
    """Join assets to exact source-geometry hazard rows (same logic as portfolio)."""
    con = DuckDBConnection.for_analytics(
        work_dir, extensions=("spatial", "h3")
    ).connect()
    return con.execute(
        f"""
        SELECT a.asset_id, a.sector, a.replacement_value,
               a.longitude, a.latitude, h.*
        FROM read_parquet({sql_quote(str(assets_path))}) a
        JOIN read_parquet({sql_quote(str(hazard_path))}) h
          ON h3_latlng_to_cell(a.latitude, a.longitude, {h3_resolution}) = h.cell_index
         AND (h.source_geometry IS NULL
              OR ST_Covers(
                     ST_GeomFromWKB(h.source_geometry),
                     ST_Point(a.longitude, a.latitude)
                 ))
        WHERE h.hazard_name = {sql_quote(HAZARD_NAME)}
          AND h.horizon = {HORIZON}
          AND h.pathway = {sql_quote(PATHWAY)}
        """
    ).arrow().read_all()


def main() -> None:
    args = parse_args()
    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    assets_path: Path = args.asset_input
    hazard_path: Path = args.hazard_input
    matched_path = output_dir / "assets_matched_hazard.parquet"
    risk_path = output_dir / "portfolio_risk_levels.parquet"

    assets = pq.read_table(assets_path)
    hazard = read_hazard_dataset(hazard_path)
    metadata = read_hazard_metadata(hazard_path)
    print(f"assets: {assets.num_rows} <- {assets_path}")
    print(f"hazard: {hazard.num_rows} rows <- {hazard_path}")

    matched = match_assets_to_hazard(
        assets_path,
        hazard_path,
        h3_resolution=metadata.h3_resolution,
        work_dir=output_dir,
    )
    if matched.num_rows != assets.num_rows:
        raise RuntimeError(
            f"expected {assets.num_rows} matched assets, found {matched.num_rows}"
        )
    pq.write_table(matched, matched_path, compression="zstd")

    outcomes = []
    for row in matched.to_pylist():
        exposure = distribution_from_hazard_row(row)
        suite = generate_microscores(
            exposure,
            impact=DEPTH_DAMAGE,
            probabilities=MICROSCORE_PROBABILITIES,
            metadata=ScenarioMetadata(
                factor=row["asset_id"],
                pathway=PATHWAY,
                horizon=HORIZON,
            ),
        )
        binary = suite.at(args.design_probability)
        outcomes.append(
            replace(
                binary,
                factor=row["asset_id"],
                weight=1.0,
                downside_impact=float(binary.downside_impact)
                * float(row["replacement_value"]),
            )
        )
        print(
            f"{row['asset_id']}: downside_p={binary.downside_probability:.4f}, "
            f"damage_ratio={binary.downside_impact:.4f}, "
            f"downside_$={outcomes[-1].downside_impact:,.0f}"
        )

    risk = compute_risk(outcomes, levels=RISK_LEVELS)
    print(f"spanning branches: {risk.branch_count}")
    rows = []
    for level in risk.levels:
        print(f"p={level.probability}: VaR={level.var:,.0f}  CVaR={level.cvar:,.0f}")
        for item in level.attribution:
            rows.append(
                {
                    "probability": level.probability,
                    "var": level.var,
                    "cvar": level.cvar,
                    "factor": item.factor,
                    "var_impact": item.var_impact,
                    "cvar_impact": item.cvar_impact,
                }
            )
            print(
                f"  {item.factor}: var_impact={item.var_impact:,.0f}, "
                f"cvar_impact={item.cvar_impact:,.0f}"
            )

    pq.write_table(pa.Table.from_pylist(rows), risk_path, compression="zstd")
    print(f"wrote {matched_path}")
    print(f"wrote {risk_path}")


if __name__ == "__main__":
    main()
