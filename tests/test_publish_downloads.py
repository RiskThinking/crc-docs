"""The map pipelines copy their files into the chat host's downloads folder."""

from __future__ import annotations

import importlib

import pytest

MODULES = (
    "pipelines.which_sites_are_most_at_risk",
    "pipelines.how_exposed_is_this_company",
)


@pytest.mark.parametrize("name", MODULES)
def test_publish_downloads_copies_into_the_first_host_folder(
    name, tmp_path, monkeypatch, capsys
):
    module = importlib.import_module(name)
    host = tmp_path / "mnt-data"
    host.mkdir()
    monkeypatch.setattr(module, "HOST_DOWNLOADS", (tmp_path / "missing", host))
    source = tmp_path / "page.html"
    source.write_text("<html></html>")

    module.publish_downloads({"my-map.html": source, "absent.geojson": tmp_path / "x"})

    assert (host / "my-map.html").read_text() == "<html></html>"
    assert not (host / "absent.geojson").exists()
    out = capsys.readouterr().out
    assert f"Download file: {host / 'my-map.html'}" in out
    assert "do not write links" in out


@pytest.mark.parametrize("name", MODULES)
def test_publish_downloads_does_nothing_without_a_host_folder(
    name, tmp_path, monkeypatch, capsys
):
    module = importlib.import_module(name)
    monkeypatch.setattr(module, "HOST_DOWNLOADS", (tmp_path / "missing",))
    source = tmp_path / "page.html"
    source.write_text("x")
    module.publish_downloads({"my-map.html": source})
    assert capsys.readouterr().out == ""
