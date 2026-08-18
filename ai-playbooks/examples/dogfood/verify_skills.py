#!/usr/bin/env python3
"""Offline dogfood suite for target flexibility across all bundled Agent Skills."""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from crc_sdk.connectors import read_hazard_dataset, read_hazard_metadata
from crc_sdk.connectors.parquet import hazard_arrow_schema, write_hazard_dataset
from crc_sdk.types import SourceProvenance

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[3]
SKILLS = ROOT / ".agents" / "skills"
HAZARD_FIXTURE = ROOT / "fixtures" / "os_climate" / "hazard.parquet"


class Record:
    """Small Pydantic-like object for deterministic VELO API doubles."""

    def __init__(self, **values: Any) -> None:
        self.__dict__.update(values)

    def model_dump(self, **_: Any) -> dict[str, Any]:
        def convert(value: Any) -> Any:
            if isinstance(value, Record):
                return value.model_dump()
            if isinstance(value, list):
                return [convert(item) for item in value]
            return value

        return {key: convert(value) for key, value in self.__dict__.items()}


class FakeClimate:
    def list_pathways(self) -> list[str]:
        return ["ssp245", "ssp585"]

    def list_horizons(self) -> list[int]:
        return [2050, 2070]


class FakeAssets:
    def __init__(self) -> None:
        self.items = {
            "asset-a": Record(
                id="asset-a",
                name="Alpha Warehouse",
                address="1 Alpha Road",
                latitude=50.9375,
                longitude=6.9603,
                asset_type="warehouse",
            ),
            "asset-b": Record(
                id="asset-b",
                name="Beta Plant",
                address="2 Beta Road",
                latitude=43.65,
                longitude=-79.38,
                asset_type="factory",
            ),
        }

    def get_asset(self, asset_id: str) -> Record:
        return self.items[asset_id]

    def search_assets(self, query: str) -> list[Record]:
        query = query.lower()
        return [item for item in self.items.values() if query in item.name.lower()]

    def get_asset_owner(self, asset_id: str) -> Record:
        suffix = asset_id[-1]
        return Record(id=f"company-{suffix}", name=f"Company {suffix.upper()}")


class FakeCompanies:
    def get_company(self, company_id: str) -> Record:
        return Record(id=company_id, name=f"Company {company_id[-1].upper()}")

    def list_company_asset_climate_scores(
        self, company_id: str, pathway: str, horizon: int
    ) -> list[Record]:
        suffix = company_id[-1]
        return [
            Record(
                asset_id=f"asset-{suffix}",
                dcr_score=0.2 if suffix == "a" else 0.6,
                cvar_95=0.3 if suffix == "a" else 0.8,
                pathway=pathway,
                horizon=horizon,
            )
        ]

    def list_company_asset_impact_scores(
        self, company_id: str, pathway: str, horizon: int
    ) -> list[Record]:
        suffix = company_id[-1]
        return [
            Record(
                asset_id=f"asset-{suffix}",
                index_risks=[
                    Record(
                        index_name="flood" if suffix == "a" else "heat",
                        index_impact_cvar_50=0.1 if suffix == "a" else 0.4,
                    )
                ],
                pathway=pathway,
                horizon=horizon,
            )
        ]

    def list_uninsurable_company_assets(
        self, company_id: str, _pathway: str, _horizon: int
    ) -> list[Record]:
        return [] if company_id.endswith("a") else [Record(asset_id="asset-b", cvar_95=0.8)]

    def list_stranded_company_assets(
        self, company_id: str, _pathway: str, _horizon: int
    ) -> list[Record]:
        return [] if company_id.endswith("a") else [Record(asset_id="asset-b", cvar_95=0.8)]

    def get_company_climate_scores(
        self, company_id: str, _pathway: str, _horizon: int
    ) -> Record:
        return Record(dcr_score=0.25 if company_id.endswith("a") else 0.65, cvar_95=0.3)

    def get_company_impact_scores(
        self, company_id: str, _pathway: str, _horizon: int
    ) -> list[Record]:
        return [Record(index_name="flood", index_impact_cvar_95=0.1 if company_id.endswith("a") else 0.5)]

    def aggregate_company_asset_climate_scores_by_country(
        self, company_id: str, _pathway: str, _horizon: int
    ) -> list[Record]:
        return [Record(country="DEU" if company_id.endswith("a") else "CAN", asset_count=1, dcr_score=0.4)]

    def aggregate_company_asset_climate_scores_by_asset_type(
        self, company_id: str, _pathway: str, _horizon: int
    ) -> list[Record]:
        return [Record(asset_type="warehouse" if company_id.endswith("a") else "factory", asset_count=1, dcr_score=0.4)]


class FakeMarkets:
    def get_index(self, index_id: str) -> Record:
        return Record(id=index_id, name="Synthetic Industrial Index")

    def get_index_climate_scores(
        self, _index_id: str, _pathway: str, _horizon: int
    ) -> Record:
        return Record(dcr_score=0.55, cvar_95=0.5)

    def get_index_impact_scores(
        self, _index_id: str, _pathway: str, _horizon: int
    ) -> list[Record]:
        return [Record(index_name="heat", index_impact_cvar_95=0.35)]

    def aggregate_index_asset_climate_scores_by_country(
        self, _index_id: str, _pathway: str, _horizon: int
    ) -> list[Record]:
        return [Record(country="USA", asset_count=20, dcr_score=0.55)]

    def aggregate_index_asset_climate_scores_by_asset_type(
        self, _index_id: str, _pathway: str, _horizon: int
    ) -> list[Record]:
        return [Record(asset_type="factory", asset_count=20, dcr_score=0.55)]


class FakeClient:
    def __init__(self) -> None:
        self.climate = FakeClimate()
        self.assets = FakeAssets()
        self.companies = FakeCompanies()
        self.markets = FakeMarkets()


def command(*parts: str | Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(part) for part in parts],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )


def load_module(path: Path) -> Any:
    module_name = "dogfood_" + "_".join(path.with_suffix("").parts[-3:])
    module_name = module_name.replace("-", "_")
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_script(skill: str, filename: str) -> Any:
    return load_module(SKILLS / skill / "scripts" / filename)


def run_mocked(module: Any, argv: list[str], client: FakeClient) -> None:
    old_argv = sys.argv
    old_client = module.APIClient
    try:
        module.APIClient = lambda: client
        sys.argv = [str(module.__file__), *argv]
        result = module.main()
        if result not in (None, 0):
            raise AssertionError(f"unexpected return code {result}")
    finally:
        module.APIClient = old_client
        sys.argv = old_argv


def write_asset_targets(directory: Path) -> tuple[Path, Path]:
    rows = [
        {
            "asset_id": "synthetic-dogfood-a",
            "longitude": "6.9603",
            "latitude": "50.9375",
            "asset_name": "Synthetic Cologne A",
        },
        {
            "asset_id": "synthetic-dogfood-b",
            "longitude": "6.96031",
            "latitude": "50.93751",
            "asset_name": "Synthetic Cologne B",
        },
        {
            "asset_id": "synthetic-dogfood-c",
            "longitude": "6.96029",
            "latitude": "50.93749",
            "asset_name": "Synthetic Cologne C",
        },
    ]
    fieldnames = list(rows[0])

    first = directory / "portfolio-alpha.csv"
    second = directory / "portfolio-beta.csv"
    for path, selected in ((first, rows[:1]), (second, rows[1:])):
        with path.open("w", newline="") as target:
            writer = csv.DictWriter(target, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(selected)
    return first, second


def synthetic_drought(destination: Path) -> Path:
    source = read_hazard_dataset(HAZARD_FIXTURE)
    metadata = read_hazard_metadata(HAZARD_FIXTURE)
    rows = []
    for original in source.to_pylist():
        row = dict(original)
        row["hazard_name"] = "SyntheticDroughtIndex"
        row["source_id"] = f"{row['source_id']}-synthetic-drought"
        rows.append(row)
    drought_metadata = metadata.model_copy(
        update={
            "return_period_tail": "lower",
            "value_unit": "index",
            "value_semantics": "synthetic drought index for dogfood only",
            "producer": "crc-docs-dogfood",
            "source": SourceProvenance(
                provider="synthetic",
                dataset="drought-flexibility-fixture",
                version="1",
            ),
        }
    )
    table = pa.Table.from_pylist(rows, schema=hazard_arrow_schema(drought_metadata))
    write_hazard_dataset(table, destination, drought_metadata, max_workers=1)
    return destination


def multi_scenario_flood(destination: Path) -> Path:
    source = read_hazard_dataset(HAZARD_FIXTURE)
    metadata = read_hazard_metadata(HAZARD_FIXTURE)
    rows = source.to_pylist()
    for original in source.to_pylist():
        row = dict(original)
        row["pathway"] = "synthetic-stress"
        row["horizon"] = 2050
        row["curve_location"] += 0.75
        rows.append(row)
    scenario_metadata = metadata.model_copy(
        update={
            "producer": "crc-docs-dogfood",
            "source": SourceProvenance(
                provider="synthetic",
                dataset="multi-scenario-flood-selection-fixture",
                version="1",
            ),
        }
    )
    table = pa.Table.from_pylist(rows, schema=hazard_arrow_schema(scenario_metadata))
    write_hazard_dataset(table, destination, scenario_metadata, max_workers=1)
    return destination


def dogfood_mortgage(directory: Path, assets: Path) -> dict[str, Any]:
    script = SKILLS / "crc-screen-mortgage-flood" / "scripts" / "screen_mortgage_flood.py"
    skill_module = load_module(script)
    pipeline_module = load_module(ROOT / "pipelines" / "jrc_flood_pipeline.py")
    skill_resolution = skill_module.parser().get_default("h3_resolution")
    pipeline_resolution = pipeline_module.parser().get_default("h3_resolution")
    assert skill_resolution == pipeline_resolution == 9
    common = [sys.executable, script, "--assets", assets, "--cache", directory / "cache", "--output", directory / "unused.parquet", "--plan-only"]
    europe = command(*common, "--dataset", "efas", "--bounds", "6.8", "50.8", "7.7", "51.1")
    canada = command(*common, "--dataset", "glofas", "--bounds", "-79.7", "43.5", "-79.1", "43.9")
    assert "cems-efas" in europe.stdout and "cems-glofas" in canada.stdout
    return {"skill": "crc-screen-mortgage-flood", "targets": ["EFAS/Cologne AOI", "GloFAS/Toronto AOI"], "h3_resolution": skill_resolution, "result": "pass"}


def dogfood_loss(directory: Path, portfolios: tuple[Path, Path]) -> dict[str, Any]:
    script = SKILLS / "crc-model-flood-insurance-loss" / "scripts" / "model_flood_loss.py"
    hazard = multi_scenario_flood(directory / "multi-scenario-flood.parquet")
    outputs = [directory / "loss-alpha.parquet", directory / "loss-beta.parquet"]
    command(sys.executable, script, "--hazard", hazard, "--assets", portfolios[0], "--output", outputs[0], "--periods", "25", "100", "--pathway", "historical", "--horizon", "1980", "--depth-knots", "0,0.2,1,2", "--damage-knots", "0,0,0.25,1", "--workers", "1")
    command(sys.executable, script, "--hazard", hazard, "--assets", portfolios[1], "--output", outputs[1], "--periods", "50", "500", "--pathway", "synthetic-stress", "--horizon", "2050", "--depth-knots", "0,0.5,1.5,3", "--damage-knots", "0,0.1,0.5,1", "--workers", "1")
    alpha = pq.read_table(outputs[0])
    beta = pq.read_table(outputs[1])
    assert alpha.num_rows == 1 and set(alpha["pathway"].to_pylist()) == {"historical"} and set(alpha["horizon"].to_pylist()) == {1980}
    assert beta.num_rows == 2 and set(beta["pathway"].to_pylist()) == {"synthetic-stress"} and set(beta["horizon"].to_pylist()) == {2050}
    return {"skill": "crc-model-flood-insurance-loss", "targets": ["historical/1980 single warehouse", "synthetic-stress/2050 two assets"], "result": "pass"}


def dogfood_portfolio(directory: Path, portfolios: tuple[Path, Path]) -> tuple[dict[str, Any], Path, Path]:
    script = SKILLS / "crc-assess-asset-portfolio-risk" / "scripts" / "assess_asset_portfolio.py"
    drought = synthetic_drought(directory / "synthetic-drought.parquet")
    output_a = directory / "portfolio-alpha"
    output_b = directory / "portfolio-beta"
    command(sys.executable, script, "--assets", portfolios[0], "--hazard", f"flood={HAZARD_FIXTURE}", "--output-dir", output_a, "--periods", "25", "100", "--pathway", "historical", "--horizon", "1980", "--workers", "1")
    command(sys.executable, script, "--assets", portfolios[1], "--hazard", f"flood={HAZARD_FIXTURE}", "--hazard", f"drought={drought}", "--output-dir", output_b, "--periods", "50", "500", "--pathway", "historical", "--horizon", "1980", "--workers", "1")
    assert pq.read_table(output_a / "flood.parquet").num_rows == 1
    assert pq.read_table(output_b / "flood.parquet").num_rows == 2
    assert pq.read_table(output_b / "drought.parquet").num_rows == 2
    evidence = {"skill": "crc-assess-asset-portfolio-risk", "targets": ["one-asset flood book", "two-asset flood+drought book"], "result": "pass"}
    return evidence, output_a / "flood.parquet", output_b / "drought.parquet"


def dogfood_property(directory: Path, client: FakeClient) -> tuple[dict[str, Any], Path, Path]:
    module = load_script("velo-underwrite-property-climate", "underwrite_property.py")
    output_a = directory / "property-alpha.json"
    output_b = directory / "property-beta.json"
    run_mocked(module, ["--asset-id", "asset-a", "--pathway", "ssp245", "--horizon", "2050", "--output", str(output_a)], client)
    run_mocked(module, ["--query", "Beta", "--pathway", "ssp585", "--horizon", "2070", "--output", str(output_b)], client)
    alpha = json.loads(output_a.read_text())
    beta = json.loads(output_b.read_text())
    assert alpha["asset"]["id"] == "asset-a" and beta["asset"]["id"] == "asset-b"
    evidence = {"skill": "velo-underwrite-property-climate", "targets": ["asset ID/Cologne warehouse/2050", "search/Toronto plant/2070"], "result": "pass (API double)"}
    return evidence, output_a, output_b


def dogfood_insurability(directory: Path, client: FakeClient) -> dict[str, Any]:
    module = load_script("velo-triage-portfolio-insurability", "triage_insurability.py")
    output_a = directory / "insurability-alpha.json"
    output_b = directory / "insurability-beta.json"
    run_mocked(module, ["--company-id", "company-a", "--pathway", "ssp245", "--horizon", "2050", "--output", str(output_a)], client)
    run_mocked(module, ["--company-id", "company-b", "--pathway", "ssp585", "--horizon", "2070", "--output", str(output_b)], client)
    alpha = json.loads(output_a.read_text())
    beta = json.loads(output_b.read_text())
    assert alpha["counts"]["uninsurable"] == 0 and beta["counts"]["uninsurable"] == 1
    return {"skill": "velo-triage-portfolio-insurability", "targets": ["Company A/2050", "Company B/2070"], "result": "pass (API double)"}


def dogfood_company(directory: Path, client: FakeClient) -> tuple[dict[str, Any], Path]:
    module = load_script("velo-assess-company-climate-risk", "assess_company.py")
    company_output = directory / "company.json"
    index_output = directory / "index.json"
    run_mocked(module, ["--company-id", "company-a", "--pathway", "ssp245", "--horizon", "2050", "--output", str(company_output)], client)
    run_mocked(module, ["--index-id", "index-industrials", "--pathway", "ssp585", "--horizon", "2070", "--output", str(index_output)], client)
    company = json.loads(company_output.read_text())
    index = json.loads(index_output.read_text())
    assert company["target_type"] == "company" and index["target_type"] == "market_index"
    evidence = {"skill": "velo-assess-company-climate-risk", "targets": ["single company", "market index"], "result": "pass (API double)"}
    return evidence, index_output


def dogfood_compare(directory: Path, crc_outputs: tuple[Path, Path], velo_outputs: tuple[Path, Path]) -> dict[str, Any]:
    script = SKILLS / "compare-crc-velo-assessments" / "scripts" / "inventory_assessments.py"
    first = directory / "compare-property.json"
    second = directory / "compare-index.json"
    command(sys.executable, script, "--crc", crc_outputs[0], "--velo", velo_outputs[0], "--output", first)
    command(sys.executable, script, "--crc", crc_outputs[1], "--velo", velo_outputs[1], "--output", second)
    first_result = json.loads(first.read_text())
    second_result = json.loads(second.read_text())
    assert first_result["classification"] == second_result["classification"] == "inventory_only"
    assert first_result["velo"]["top_level_fields"] != second_result["velo"]["top_level_fields"]
    return {"skill": "compare-crc-velo-assessments", "targets": ["flood/property pair", "drought/market-index pair"], "result": "pass"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, help="Optional JSON evidence output")
    args = parser.parse_args()

    for skill in SKILLS.iterdir():
        if skill.is_dir() and not (skill / "SKILL.md").is_file():
            raise AssertionError(f"missing SKILL.md: {skill}")

    with tempfile.TemporaryDirectory(prefix="crc-skill-dogfood-") as raw_directory:
        directory = Path(raw_directory)
        portfolios = write_asset_targets(directory)
        evidence: list[dict[str, Any]] = []
        evidence.append(dogfood_mortgage(directory, portfolios[0]))
        evidence.append(dogfood_loss(directory, portfolios))
        portfolio_evidence, crc_a, crc_b = dogfood_portfolio(directory, portfolios)
        evidence.append(portfolio_evidence)

        client = FakeClient()
        property_evidence, property_a, _property_b = dogfood_property(directory, client)
        evidence.append(property_evidence)
        evidence.append(dogfood_insurability(directory, client))
        company_evidence, index_output = dogfood_company(directory, client)
        evidence.append(company_evidence)
        evidence.append(dogfood_compare(directory, (crc_a, crc_b), (property_a, index_output)))

    report = {"status": "pass", "skills_tested": len(evidence), "evidence": evidence}
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered)
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
