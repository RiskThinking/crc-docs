from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.build_map_page import build, find_bundle, layer_config

GEOJSON = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [-82.5, 28.0]},
            "properties": {
                "city": "Tampa</script>",
                "hurricanes_within_50km_since_1990": 2,
            },
        }
    ],
}


def test_layer_config_colours_by_hurricanes() -> None:
    (layer,) = layer_config(GEOJSON)
    assert layer["id"] == "points"
    assert layer["visKey"] == "hurricanes_within_50km_since_1990"


def test_build_writes_page_with_inline_data(tmp_path: Path) -> None:
    viz = tmp_path / "viz"
    viz.mkdir()
    (viz / "crc-viz.js").write_text("window.CrcViz = {}; // </script>")
    (viz / "crc-viz.css").write_text("")
    source = tmp_path / "locations.geojson"
    source.write_text(json.dumps(GEOJSON))
    page = build(source, viz, tmp_path / "map", "Test").read_text()
    assert "CrcViz.mountHazardMap" in page
    assert "Tampa</script>" not in page  # escaped, cannot end the script early
    assert "window.CrcViz = {}" in page  # bundle is inline, not linked
    assert "src=" not in page and "stylesheet" not in page
    assert [p.name for p in (tmp_path / "map").iterdir()] == ["index.html"]


def test_build_needs_the_bundle(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        build(tmp_path / "x.geojson", tmp_path, tmp_path / "map", "Test")


def test_find_bundle_prefers_explicit_folder(tmp_path: Path) -> None:
    (tmp_path / "crc-viz.js").write_text("")
    assert find_bundle(tmp_path, download=False) == tmp_path


def test_repository_bundle_is_committed() -> None:
    folder = find_bundle(download=False)
    assert folder is not None
    assert (folder / "crc-viz.js").stat().st_size > 1_000_000
    assert (folder / "crc-viz.css").is_file()


def test_page_template_keeps_js_newline_escapes():
    from tools.build_map_page import PAGE

    # A bare "\n" in PAGE becomes a real line break inside a JS string literal.
    assert 'problems.join("\\n")' in PAGE


def test_tooltip_lists_the_damage_values():
    from tools.build_map_page import layer_config

    props = {
        "city": "x",
        "hurricanes_within_50km_since_1990": 2,
        "total_early": 0.5,
        "total_late": 1.4,
    }
    geojson = {"features": [{"properties": props}]}
    tooltip = layer_config(geojson)[0]["tooltip"]
    assert tooltip["footerKeys"] == ["total_early", "total_late"]
    assert "2070-2080" in tooltip["keyAliases"]["total_late"]
    only_damage = {"features": [{"properties": {"city": "x", "total_late": 1.4}}]}
    assert layer_config(only_damage)[0]["tooltip"]["footerKeys"] == [
        "total_early",
        "total_late",
    ]
