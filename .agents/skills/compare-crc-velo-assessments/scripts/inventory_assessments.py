#!/usr/bin/env python3
"""Inventory CRC Parquet and VELO JSON evidence without asserting metric equivalence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq


def decode_metadata(raw: dict[bytes, bytes] | None) -> dict[str, Any]:
    decoded: dict[str, Any] = {}
    for key, value in (raw or {}).items():
        text = value.decode("utf-8", errors="replace")
        try:
            decoded[key.decode("utf-8", errors="replace")] = json.loads(text)
        except json.JSONDecodeError:
            decoded[key.decode("utf-8", errors="replace")] = text
    return decoded


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--crc", required=True, type=Path, help="CRC evaluation Parquet")
    p.add_argument("--velo", required=True, type=Path, help="VELO JSON export")
    p.add_argument("--output", required=True, type=Path)
    return p


def main() -> int:
    args = parser().parse_args()
    parquet = pq.ParquetFile(args.crc)
    velo = json.loads(args.velo.read_text())
    result = {
        "classification": "inventory_only",
        "non_equivalence_warning": "CRC return-period hazard/impact values must not be compared directly with VELO DCR, expected impact, VaR, or CVaR without a proven semantic crosswalk.",
        "crc": {
            "path": str(args.crc),
            "rows": parquet.metadata.num_rows,
            "columns": parquet.schema_arrow.names,
            "metadata": decode_metadata(parquet.schema_arrow.metadata),
        },
        "velo": {"path": str(args.velo), "top_level_fields": sorted(velo), "evidence": velo},
        "alignment_required": ["asset/entity", "hazard/factor", "pathway", "horizon", "metric", "unit", "spatial precision", "source/model version"],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

