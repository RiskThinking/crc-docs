#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd -- "$script_dir/../.." && pwd)"

if [[ $# -ne 0 && $# -ne 5 && $# -ne 6 ]]; then
  echo "usage: $0 [efas|glofas MIN_LON MIN_LAT MAX_LON MAX_LAT [OUTPUT_DIR]]" >&2
  exit 2
fi

dataset="${1:-efas}"
min_lon="${2:-6.95}"
min_lat="${3:-50.93}"
max_lon="${4:-6.97}"
max_lat="${5:-50.95}"
output_dir="${6:-$repo_root/pipeline_output/ai-playbooks}"

if [[ "$dataset" != "efas" && "$dataset" != "glofas" ]]; then
  echo "dataset must be efas or glofas" >&2
  exit 2
fi

cd "$repo_root"
mkdir -p "$output_dir"

echo "Materializing canonical JRC $dataset flood data for the selected bounds..."
uv run python pipelines/jrc_flood_pipeline.py \
  --dataset "$dataset" \
  --bounds "$min_lon" "$min_lat" "$max_lon" "$max_lat" \
  --return-periods 25 100 500 \
  --output-dir "$output_dir"

echo "Sourcing Overture candidates inside the JRC coverage..."
uv run python pipelines/overture_assets_pipeline.py \
  --bounds "$min_lon" "$min_lat" "$max_lon" "$max_lat" \
  --coverage-hazard "$output_dir/jrc_depths_by_cell.parquet" \
  --limit 10 \
  --output "$output_dir/overture-assets.csv"

echo "Screening the Overture candidates against canonical JRC flood data..."
uv run python .agents/skills/crc-screen-mortgage-flood/scripts/screen_mortgage_flood.py \
  --assets "$output_dir/overture-assets.csv" \
  --hazard "$output_dir/jrc_depths_by_cell.parquet" \
  --output "$output_dir/mortgage-flood.parquet" \
  --periods 25 100 500 \
  --workers 1

echo "Running the offline illustrative insurance-loss assessment..."
uv run python .agents/skills/crc-model-flood-insurance-loss/scripts/model_flood_loss.py \
  --assets "$output_dir/overture-assets.csv" \
  --hazard "$output_dir/jrc_depths_by_cell.parquet" \
  --pathway historical \
  --horizon 0 \
  --depth-knots 0,0.2,1,2 \
  --damage-knots 0,0,0.25,1 \
  --periods 25 100 250 500 \
  --output "$output_dir/flood-loss.parquet"

echo "Running the offline CRC asset-portfolio assessment..."
uv run python .agents/skills/crc-assess-asset-portfolio-risk/scripts/assess_asset_portfolio.py \
  --assets "$output_dir/overture-assets.csv" \
  --hazard flood="$output_dir/jrc_depths_by_cell.parquet" \
  --periods 25 100 500 \
  --pathway historical \
  --horizon 0 \
  --output-dir "$output_dir/portfolio"

echo "Inventorying CRC output beside a clearly synthetic VELO-shaped example..."
uv run python .agents/skills/compare-crc-velo-assessments/scripts/inventory_assessments.py \
  --crc "$output_dir/flood-loss.parquet" \
  --velo ai-playbooks/examples/velo-company-example.json \
  --output "$output_dir/comparison-inventory.json"

echo "Demo complete. Outputs: $output_dir"
