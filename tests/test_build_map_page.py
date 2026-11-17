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


def test_link_round_trips_every_numeric_field():
    from tools.build_map_page import decode_link, encode_link

    props = {
        "asset_id": "a1",
        "name": "Target",
        "city": "Miami",
        "hurricanes_within_50km_since_1990": 3,
        "storm_damage_2025_2035": 0.12344,
        "hot_weather_damage_2070_2080": 0.8,
        "total_damage_2025_2035": 0.5,
        "total_damage_2070_2080": 1.4,
    }
    geojson = {
        "features": [
            {
                "geometry": {"type": "Point", "coordinates": [-80.1234, 26.5]},
                "properties": props,
            }
        ]
    }
    link = encode_link(geojson)
    assert link.startswith("https://") and "#" in link
    pack = decode_link(link)
    assert pack["k"] == [
        "hurricanes_within_50km_since_1990",
        "storm_damage_2025_2035",
        "hot_weather_damage_2070_2080",
        "total_damage_2025_2035",
        "total_damage_2070_2080",
    ]
    assert pack["r"] == [[-80.123, 26.5, "Miami", 3, 0.1234, 0.8, 0.5, 1.4]]


def test_viewer_reads_the_link(tmp_path):
    from tools.build_map_page import build_viewer, find_bundle

    viz = find_bundle(download=False)
    page = build_viewer(viz, tmp_path).read_text()
    assert "location.hash" in page and "DecompressionStream" in page
    assert "__hurricanes__" in page


SITES_GEOJSON = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [-112.07, 33.45]},
            "properties": {
                "title": "Warehouse 1 (Phoenix)",
                "tx_max_2025_2035": 46.1,
                "tx_max_2070_2080": 50.2,
                "tx_max_change": 4.1,
                "hot_days_change": 60.0,
            },
        }
    ],
}


def test_layer_config_colours_sites_by_hottest_day_change() -> None:
    (layer,) = layer_config(SITES_GEOJSON)
    assert layer["visKey"] == "tx_max_change"
    assert layer["fieldInfo"]["rx1day_change"]["unit"] == "mm"


def test_layer_config_labels_cdt_pathway_fields_with_units() -> None:
    (layer,) = layer_config(SITES_GEOJSON)
    info = layer["fieldInfo"]
    assert info["tx_max_ssp126_change"] == {
        "label": "Hottest day SSP1-2.6 change",
        "unit": "°C",
    }
    assert info["hot_days_ssp585_change"]["unit"] == "days"
    assert info["tx_max_baseline"]["label"] == "Hottest day baseline"
    assert info["rx1day_ssp245_2070_2090"] == {
        "label": "Wettest day SSP2-4.5 2070-2090",
        "unit": "mm",
    }
    assert layer["tooltip"]["keyAliases"]["rx1day_ssp245_change"] == (
        "Wettest day SSP2-4.5 change"
    )
    assert not any("fwi_ssp" in key for key in info)


def test_layer_config_gives_unlisted_hazard_fields_their_unit() -> None:
    feature = {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [-119.8, 36.8]},
        "properties": {
            "tx_max_change": 7.1,
            "tx_max_historic_2010": 43.4,
            "hot_days_historic_2010": 44,
            "rx1day_historic_2010": 50.3,
            "title": "Fresno",
        },
    }
    (layer,) = layer_config({"type": "FeatureCollection", "features": [feature]})
    info = layer["fieldInfo"]
    assert info["tx_max_historic_2010"]["unit"] == "°C"
    assert info["hot_days_historic_2010"]["unit"] == "days"
    assert info["rx1day_historic_2010"]["unit"] == "mm"
    assert "title" not in info


def test_sites_geojson_matches_the_map_fields() -> None:
    from pipelines.which_sites_are_most_at_risk import sites_geojson
    from tools.build_map_page import SITE_HAZARDS

    sites = [{"site": "Phoenix", "latitude": 33.45, "longitude": -112.07}]
    table = {
        "Phoenix": {h: {"early": 1.0, "late": 3.0, "change": 2.0} for h in SITE_HAZARDS}
    }
    (feature,) = sites_geojson(sites, table)["features"]
    assert feature["geometry"]["coordinates"] == [-112.07, 33.45]
    props = feature["properties"]
    assert props["title"] == props["site"] == "Phoenix"
    assert {
        f"{h}_{w}" for h in SITE_HAZARDS for w in ("2025_2035", "2070_2080", "change")
    } <= set(props)
    (layer,) = layer_config({"features": [feature]})
    assert layer["visKey"] in props


def test_viewer_offers_a_sites_layer(tmp_path):
    from tools.build_map_page import build_viewer, find_bundle

    page = build_viewer(find_bundle(download=False), tmp_path).read_text()
    assert '"sites"' in page and "tx_max_change" in page


def test_site_title_combines_site_and_city() -> None:
    from pipelines.which_sites_are_most_at_risk import sites_geojson
    from tools.build_map_page import decode_link, encode_link

    sites = [
        {"site": "Store 12", "city": "Tampa", "latitude": 27.9, "longitude": -82.4},
        {"site": "Tampa DC", "city": "Tampa", "latitude": 28.0, "longitude": -82.5},
        {"site": "Plain", "latitude": 29.0, "longitude": -82.0},
    ]
    geojson = sites_geojson(sites, {})
    titles = [f["properties"]["title"] for f in geojson["features"]]
    assert titles == ["Store 12 (Tampa)", "Tampa DC", "Plain"]
    assert [r[2] for r in decode_link(encode_link(geojson))["r"]] == titles


def test_hosted_viewer_labels_site_fields_it_only_learns_from_the_link(tmp_path):
    from tools.build_map_page import build_viewer, find_bundle

    page = build_viewer(find_bundle(download=False), tmp_path).read_text()
    assert 'const hazards = {"tx_max": ["Hottest day", "\\u00b0C"]' in page
    assert "layer.fieldInfo[k] = " in page


def test_layer_config_labels_hazard_fields_that_only_later_sites_have() -> None:
    first = {"properties": {"title": "A", "tx_max_change": 1.0}}
    later = {"properties": {"title": "B", "tx_max_change": 2.0, "tx_max_late": 3.0}}
    (layer,) = layer_config({"features": [first, later]})
    assert layer["fieldInfo"]["tx_max_late"]["unit"] == "\u00b0C"


def test_layer_config_styles_sites_when_only_a_later_site_has_the_change() -> None:
    first = {"properties": {"title": "A", "tx_max_baseline": 33.0}}
    later = {"properties": {"title": "B", "tx_max_change": 2.0}}
    (layer,) = layer_config({"features": [first, later]})
    assert layer["visKey"] == "tx_max_change"
    assert layer["fieldInfo"]["tx_max_baseline"]["unit"] == "\u00b0C"


def test_site_legend_names_the_period_of_the_data_source() -> None:
    crc = {"properties": {"title": "A", "tx_max_change": 1.0, "tx_max_2070_2080": 40.0}}
    cdt = {
        "properties": {
            "title": "A",
            "tx_max_change": 1.0,
            "tx_max_ssp585_2070_2090": 40.0,
        }
    }
    (crc_layer,) = layer_config({"features": [crc]})
    (cdt_layer,) = layer_config({"features": [cdt]})
    assert crc_layer["title"] == "Hottest day, change to 2070-2080"
    assert cdt_layer["title"] == "Hottest day, SSP5-8.5 change to 2070-2090"
