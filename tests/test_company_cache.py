import io
import json

import pyarrow as pa

from pipelines import how_exposed_is_this_company as company


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_read_json_reuses_the_cached_copy(tmp_path, monkeypatch):
    calls = []

    def fake_urlopen(url, timeout):
        calls.append(url)
        return _Response(json.dumps({"latest": "2026-10-21.0"}).encode())

    monkeypatch.setattr(company.urllib.request, "urlopen", fake_urlopen)
    first = company.read_json("https://example.test/a.json", tmp_path)
    second = company.read_json("https://example.test/a.json", tmp_path)
    assert first == second == {"latest": "2026-10-21.0"}
    assert len(calls) == 1


def test_read_json_refetches_a_stale_copy(tmp_path, monkeypatch):
    calls = []

    def fake_urlopen(url, timeout):
        calls.append(url)
        return _Response(b'{"n": 1}')

    monkeypatch.setattr(company.urllib.request, "urlopen", fake_urlopen)
    company.read_json("https://example.test/b.json", tmp_path, max_age=60)
    company.read_json("https://example.test/b.json", tmp_path, max_age=0)
    assert len(calls) == 2


class _Connection:
    def __init__(self, table):
        self.table = table
        self.queries = 0
        self.sql = ""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, parameters=None):
        if "read_parquet" in sql:
            self.queries += 1
            self.sql = sql
            self.parameters = parameters
        return self

    def to_arrow_table(self):
        return self.table


def test_find_locations_caches_the_query_result(tmp_path, monkeypatch):
    table = pa.table(
        {
            "asset_id": ["a"],
            "name": ["Apple Store"],
            "category": ["store"],
            "city": ["Miami"],
            "longitude": [-80.2],
            "latitude": [25.8],
        }
    )
    connection = _Connection(table)

    monkeypatch.setattr(company.duckdb, "connect", lambda: connection)
    monkeypatch.setattr(
        company, "overture_files", lambda bounds, cache=None: ("2026-10-21.0", ["f"])
    )
    bounds = (-87.7, 24.4, -79.9, 31.1)
    first = company.find_locations("Apple", bounds, "FL", None, tmp_path)
    second = company.find_locations("apple", bounds, "FL", None, tmp_path)
    assert first["count"] == second["count"] == 1
    assert connection.queries == 1
    other = company.find_locations("Apple", bounds, "GA", None, tmp_path)
    assert other["available"] and connection.queries == 2


def test_region_filter_accepts_both_overture_formats(tmp_path, monkeypatch):
    table = pa.table({"asset_id": ["a"]})
    connection = _Connection(table)

    monkeypatch.setattr(company.duckdb, "connect", lambda: connection)
    monkeypatch.setattr(
        company, "overture_files", lambda bounds, cache=None: ("2026-11-18.0", ["f"])
    )
    company.find_locations("Apple", (-87.7, 24.4, -79.9, 31.1), "FL", None, tmp_path)
    assert "addresses[1].region = ?" in connection.sql
    assert "LIKE '%-' || ?" in connection.sql  # 2026-11-18+ writes "US-FL"
    assert connection.parameters[-2:] == ["FL", "FL"]
