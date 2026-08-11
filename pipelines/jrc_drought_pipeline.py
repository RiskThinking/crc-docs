"""Headless JRC/EDO drought-hazard-by-H3-cell pipeline -- the notebook's scaled-up twin.

Run with:

    uv run python pipelines/jrc_drought_pipeline.py

Fits one canonical drought-severity curve per H3 cell from N years of EDO's
dekadal Soil Moisture Index (`crc_sdk.connectors.EDOIngestPolicy`/
`canonicalize_edo_drought`, the same curve-fit machinery JRC flood and
OS-Climate ingest both use, applied here to JRC/Copernicus's EDO NetCDF
files via `crc_sdk.providers.jrc_edo.EDOProvider`) -- each requested year's
own block minimum becomes one curve knot, assigned an empirical
(Gringorten plotting-position) return period rather than a literal one, the
same way an extreme-value analysis would from any other block-minima
series. Drought severity is worse at *lower* SMI, the opposite convention
from flood depth, hence `tail="lower"` throughout. The output is a real
canonical hazard Parquet (`write_hazard_stream`) -- reading it back at any
return period is a curve evaluation away
(`crc_sdk.workflows.curve_quantiles_at`). Reads stream in bounded-memory,
chunk-aligned strips per year; widen --bounds or extend --years for a
bigger run.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from crc_sdk.connectors import (
    EDOIngestPolicy,
    read_hazard_dataset,
    write_hazard_stream,
)
from crc_sdk.providers.jrc_edo import SMI, EDOProvider
from crc_sdk.workflows import curve_quantiles_at, return_periods_to_probabilities


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--bounds",
        type=float,
        nargs=4,
        default=(7.0, 49.0, 11.0, 53.0),
        metavar=("MIN_LON", "MIN_LAT", "MAX_LON", "MAX_LAT"),
        help="AOI to sample (default: %(default)s, western/central Germany)",
    )
    parser.add_argument(
        "--years",
        type=int,
        nargs=2,
        default=(2015, 2024),
        metavar=("START", "END"),
        help="Complete-year range (inclusive) to derive annual minima from "
        "(default: %(default)s). EDO's current, still-in-progress year is "
        "never included -- its filename isn't predictable without a live "
        "directory listing.",
    )
    parser.add_argument(
        "--return-periods",
        type=int,
        nargs="+",
        default=[2, 5, 10, 25],
        help="Return periods to report drought severity back at (years, "
        "default: %(default)s)",
    )
    parser.add_argument(
        "--h3-resolution",
        type=int,
        default=6,
        help="H3 resolution to fit curves at (default: %(default)s). SMI's "
        "own ~1 arcmin pixels are far finer than any reasonable H3 "
        "resolution here, so this is a modeling choice, not a raster-"
        "pixel-size-based pick.",
    )
    parser.add_argument(
        "--family",
        default="gumbel_r",
        help="Distribution family to fit each cell's severity curve "
        "against (default: %(default)s)",
    )
    parser.add_argument("--output-dir", type=Path, default=Path("pipeline_output"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    bounds = tuple(args.bounds)
    years = tuple(range(args.years[0], args.years[1] + 1))

    policy = EDOIngestPolicy(
        h3_resolution=args.h3_resolution,
        family=args.family,
        tail="lower",
        producer="crc-docs-jrc-drought-pipeline",
        creation_version="0.1.0",
        value_semantics="soil moisture index annual minimum",
        # Most pixels have too little inter-annual variance (or too few
        # valid years) to fit a meaningful severity curve; skip those
        # rather than aborting the whole run.
        on_fit_failure="skip",
    )
    provider = EDOProvider(SMI, work_dir=output_dir)
    stream = provider.canonicalize_years(years, policy, bounds=bounds)

    hazard_path = output_dir / "jrc_edo_drought_by_cell.parquet"
    write_hazard_stream(stream, hazard_path)
    print(f"wrote {hazard_path}")

    # Round-trip through the canonical contract: read back the file just
    # written (not the in-memory stream) before reconstructing severities,
    # the same way any other consumer of this Parquet would.
    table = read_hazard_dataset(hazard_path)
    cell_ids = table["cell_index"].to_pylist()
    print(f"{years[0]}-{years[-1]}: {table.num_rows:,} fitted curves")
    probabilities = return_periods_to_probabilities(args.return_periods, tail="lower")
    for rp, probability in zip(args.return_periods, probabilities):
        severities = curve_quantiles_at(table, probability)
        # One H3 cell can have more than one contributing source pixel --
        # EDO's own conservative H3 overlap coverage already produces this
        # within a single year's grid -- so cells are reduced to their
        # worst-case (minimum SMI) severity before reporting.
        by_cell: dict[int, float] = {}
        for cell_id, severity in zip(cell_ids, severities):
            if severity < by_cell.get(cell_id, float("inf")):
                by_cell[cell_id] = severity
        worst = min(by_cell.values()) if by_cell else 0.0
        print(f"  RP{rp}: {len(by_cell):,} cells, worst-case SMI {worst:.3f}")


if __name__ == "__main__":
    main()
