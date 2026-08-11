"""Headless JRC flood-hazard-by-H3-cell pipeline -- the notebook's scaled-up twin.

Run with:

    uv run python pipelines/jrc_flood_pipeline.py

Fits one canonical hazard curve per H3 cell across every requested return
period (`crc_sdk.connectors.JRCIngestPolicy`/`canonicalize_jrc_flood`, the
same curve-fit machinery OS-Climate ingest uses, applied here to JRC's own
per-tile GeoTIFFs via `crc_sdk.providers.jrc.JRCProvider`) rather than
writing one raw depth row per (cell, return period). The output is a real
canonical hazard Parquet (`write_hazard_stream`) -- reading it back at any
return period, including ones not explicitly requested here, is a curve
evaluation away (`crc_sdk.workflows.curve_quantiles_at`), the same read path
the asset-portfolio track already uses for OS-Climate data. Widen or drop
--bounds to sample a whole 10x10-degree JRC tile instead of one
neighborhood. Pixel reads happen in bounded-memory strips regardless of
raster size, so peak memory stays flat as the AOI grows.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from crc_sdk.connectors import (
    JRCIngestPolicy,
    read_hazard_dataset,
    write_hazard_stream,
)
from crc_sdk.providers.jrc import GLOFAS, JRCProvider
from crc_sdk.workflows import curve_quantiles_at, return_periods_to_probabilities


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--tile",
        default="ID54_N50_W80",
        help="JRC 10x10-degree tile id (default: %(default)s, covering Toronto)",
    )
    parser.add_argument(
        "--return-periods",
        type=int,
        nargs="+",
        default=[10, 50, 100, 500],
        help="Return periods to fit each cell's curve against, and report "
        "back at (years, default: %(default)s)",
    )
    parser.add_argument(
        "--bounds",
        type=float,
        nargs=4,
        default=None,
        metavar=("MIN_LON", "MIN_LAT", "MAX_LON", "MAX_LAT"),
        help="AOI to sample; omit to sample the whole tile",
    )
    parser.add_argument(
        "--h3-resolution",
        type=int,
        default=9,
        help="H3 resolution to fit curves at (default: %(default)s). Unlike "
        "a raw scan, curve fitting has no raster-pixel-size-based auto-pick.",
    )
    parser.add_argument(
        "--family",
        default="gumbel_r",
        help="Distribution family to fit each cell's return-level curve "
        "against (default: %(default)s)",
    )
    parser.add_argument("--output-dir", type=Path, default=Path("pipeline_output"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    bounds = tuple(args.bounds) if args.bounds else None

    policy = JRCIngestPolicy(
        h3_resolution=args.h3_resolution,
        family=args.family,
        producer="crc-docs-jrc-flood-pipeline",
        creation_version="0.1.0",
        value_semantics="riverine flood depth",
        # Most pixels in a tile never flood at any requested return period
        # and carry a constant, unfittable curve; skip those rather than
        # aborting the whole tile.
        on_fit_failure="skip",
    )
    provider = JRCProvider(GLOFAS, work_dir=output_dir)
    stream = provider.canonicalize_tile(
        args.tile, policy, return_periods=args.return_periods, bounds=bounds
    )

    hazard_path = output_dir / "jrc_depths_by_cell.parquet"
    write_hazard_stream(stream, hazard_path)
    print(f"wrote {hazard_path}")

    # Round-trip through the canonical contract: read back the file just
    # written (not the in-memory stream) before reconstructing depths, the
    # same way any other consumer of this Parquet would.
    table = read_hazard_dataset(hazard_path)
    cell_ids = table["cell_index"].to_pylist()
    print(f"{args.tile}: {table.num_rows:,} fitted curves")
    for rp, probability in zip(
        args.return_periods, return_periods_to_probabilities(args.return_periods)
    ):
        depths = curve_quantiles_at(table, probability)
        # One H3 cell can have more than one contributing source pixel --
        # JRC's own conservative H3 overlap coverage already produces this
        # within a single tile -- so cells are reduced to their worst-case
        # (max) depth before reporting.
        by_cell: dict[int, float] = {}
        for cell_id, depth in zip(cell_ids, depths):
            if depth > by_cell.get(cell_id, float("-inf")):
                by_cell[cell_id] = depth
        peak = max(by_cell.values()) if by_cell else 0.0
        print(f"  RP{rp}: {len(by_cell):,} cells, max depth {peak:.2f} m")


if __name__ == "__main__":
    main()
