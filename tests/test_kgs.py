"""Offline unit tests for the KGS ingester (no network)."""

from __future__ import annotations

from lithogpt2.ingest import kgs


def test_parse_index_comma(tmp_path):
    f = tmp_path / "ks_las_files.txt"
    f.write_text(
        "KID,API,LEASE,WELL,LATITUDE,LONGITUDE\n"
        "1044366,15-191-22590,WELLINGTON,1-28,37.31,-97.44\n"
        "1044367,15-191-22591,WELLINGTON,1-32,37.32,-97.45\n",
        encoding="utf-8",
    )
    header, rows = kgs.parse_index(f)
    assert "API" in header and "KID" in header
    assert len(rows) == 2
    assert rows[0]["API"] == "15-191-22590"


def test_parse_index_tab(tmp_path):
    f = tmp_path / "ks_las_files.tab"
    f.write_text("KID\tAPI\tLEASE\n1\t15-001-00001\tACME\n", encoding="utf-8")
    header, rows = kgs.parse_index(f)
    assert header == ["KID", "API", "LEASE"]
    assert rows[0]["LEASE"] == "ACME"


def test_fetch_archives_rejects_unknown_year():
    try:
        kgs.fetch_archives(["3000.zip"], raw_root="/tmp/nope")
        raise AssertionError("expected ValueError for unknown archive")
    except ValueError:
        pass


def test_archive_url_construction(monkeypatch, tmp_path):
    calls = []

    class FakeFetcher:
        def __init__(self, *a, **k):
            pass

        def fetch(self, url, rel_path=None, log=None):
            calls.append((url, rel_path))

    monkeypatch.setattr(kgs, "PoliteFetcher", FakeFetcher)
    kgs.fetch_archives(["2024.zip", "2014.zip"], raw_root=str(tmp_path))
    urls = [u for u, _ in calls]
    assert kgs.ARCHIVE_BASE + "2024.zip" in urls
    assert kgs.ARCHIVE_BASE + "2014.zip" in urls


def test_g1_subset_clears_target():
    total = sum(kgs.ARCHIVE_ZIPS[y][1] for y in kgs.RECOMMENDED_G1_YEARS)
    assert total > 5000  # G1 needs 5,000+ QC-passing wells; this subset clears it


def test_dry_run_returns_empty_log(capsys):
    log = kgs.ingest(dry_run=True, years=["2024.zip"])
    assert not log.ok and not log.failed
    out = capsys.readouterr().out
    assert "dry-run" in out and "2024.zip" in out
