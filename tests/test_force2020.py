"""Unit tests for the FORCE 2020 count logic (no network)."""

from __future__ import annotations

from lithogpt2.ingest.force2020 import count_wells


def test_count_wells_unique_and_rows(tmp_path):
    csv = tmp_path / "mini.csv"
    csv.write_text(
        "WELL;DEPTH_MD;GR\n"
        "15/9-13;100.0;45.1\n"
        "15/9-13;100.15;46.0\n"
        "16/1-2;200.0;60.2\n"
        "16/1-2;200.15;61.0\n"
        "16/1-2;200.30;59.5\n",
        encoding="utf-8",
    )
    n_wells, n_rows = count_wells(csv)
    assert n_wells == 2
    assert n_rows == 5


def test_count_wells_requires_well_column(tmp_path):
    csv = tmp_path / "bad.csv"
    csv.write_text("DEPTH_MD;GR\n100.0;45.1\n", encoding="utf-8")
    try:
        count_wells(csv)
        raise AssertionError("expected ValueError for missing WELL column")
    except ValueError:
        pass
