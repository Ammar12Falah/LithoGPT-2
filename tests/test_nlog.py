"""Unit tests for the NLOG index builder (no network; WFS response stubbed)."""

from __future__ import annotations

import csv

from lithogpt2.ingest import nlog


def test_mapviewer_id_parsing():
    assert nlog._mapviewer_id("https://www.nlog.nl/nlog-mapviewer/brh/872287025") == "872287025"
    assert nlog._mapviewer_id("https://www.nlog.nl/nlog-mapviewer/brh/106507070/") == "106507070"
    assert nlog._mapviewer_id(None) == ""


def test_is_released_boundary():
    from datetime import date

    on = date(2026, 7, 4)
    assert nlog._is_released("2003-01-01", on) is True
    assert nlog._is_released("2026-07-04", on) is True
    assert nlog._is_released("2027-07-05", on) is False
    assert nlog._is_released(None, on) is False


def _fake_fc():
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [4.65, 53.71]},
                "properties": {
                    "BOREHOLE_CODE": "KOL-01",
                    "BOREHOLE_NAME": "KOLLUMERLAND-01",
                    "UWI": "1476",
                    "NITG_NUMBER": "B06G0104",
                    "ON_OFFSHORE_CODE": "ON",
                    "PUBLIC_AS_OF": "2003-01-01",
                    "URL": "https://www.nlog.nl/nlog-mapviewer/brh/106507075",
                },
            },
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [4.42, 53.70]},
                "properties": {
                    "BOREHOLE_CODE": "KKP-GT-03",
                    "BOREHOLE_NAME": "KOEKOEKSPOLDER-GT-03",
                    "UWI": "5958",
                    "NITG_NUMBER": "B21D1253",
                    "ON_OFFSHORE_CODE": "ON",
                    "PUBLIC_AS_OF": "2027-07-05",
                    "URL": "https://www.nlog.nl/nlog-mapviewer/brh/3832813871",
                },
            },
        ],
    }


def test_build_index_released_only(tmp_path, monkeypatch):
    monkeypatch.setattr(nlog, "fetch_borehole_geojson", lambda **kw: _fake_fc())
    out = tmp_path / "idx.csv"
    n = nlog.build_index(str(out), released_only=True)
    assert n == 1
    rows = list(csv.DictReader(out.open(encoding="utf-8")))
    assert len(rows) == 1
    r = rows[0]
    assert r["well_id"] == "KOL-01"
    assert r["mapviewer_id"] == "106507075"
    assert r["public_as_of"] == "2003-01-01"
    assert set(r.keys()) == set(nlog.INDEX_FIELDS)


def test_build_index_include_all(tmp_path, monkeypatch):
    monkeypatch.setattr(nlog, "fetch_borehole_geojson", lambda **kw: _fake_fc())
    out = tmp_path / "idx_all.csv"
    n = nlog.build_index(str(out), released_only=False)
    assert n == 2
