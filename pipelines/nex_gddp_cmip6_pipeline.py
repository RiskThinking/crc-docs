"""Stream a NEX-GDDP-CMIP6 annual precipitation extreme to Parquet."""

from __future__ import annotations

import argparse
from pathlib import Path

import pyarrow.parquet as pq
from crc_sdk.workflows import HazardDataset


def run(output: Path, year: int = 2014) -> int:
    output.mkdir(parents=True, exist_ok=True)
    plan = (
        HazardDataset.nex_gddp_cmip6(
            "rx1day", model="ACCESS-CM2", scenario="historical", version="1.0"
        )
        .for_area((-79.5, 43.5, -79.25, 43.75))
        .years(year)
    )
    target = output / "annual_extremes.parquet"
    temporary = target.with_suffix(".tmp.parquet")
    writer = None
    count = 0
    try:
        for batch in plan.annual_extremes():
            if writer is None:
                writer = pq.ParquetWriter(temporary, batch.schema)
            writer.write_batch(batch)
            count += batch.num_rows
        if writer is None:
            raise ValueError("No valid grid cells in the selected window")
        writer.close()
        writer = None
        temporary.replace(target)
    finally:
        if writer is not None:
            writer.close()
        temporary.unlink(missing_ok=True)
    return count


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, default=2014)
    parser.add_argument("--output", type=Path, default=Path("pipeline_output/nex_gddp_cmip6"))
    args = parser.parse_args()
    print(f"Wrote {run(args.output, args.year)} grid cells")
