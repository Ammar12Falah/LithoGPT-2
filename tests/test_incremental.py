"""Tests for the incremental-resume helpers (scripts/run_qc_kgs.py uses these).

Pure pandas, no LAS dependency, so they run in any environment.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from lithogpt2.pipeline.incremental import (
    done_well_ids,
    merge_keyed,
    merge_unmapped,
    records_from_df,
)

NONE = Path("/nonexistent")


def _write(rows, path):
    merge_keyed(NONE, rows).to_csv(path, index=False)
    return path


def test_done_well_ids_empty_when_missing(tmp_path):
    assert done_well_ids(tmp_path / "absent.csv") == set()


def test_done_well_ids_reads_ids(tmp_path):
    p = _write([{"well_id": "A"}, {"well_id": "B"}], tmp_path / "rec.csv")
    assert done_well_ids(p) == {"A", "B"}


def test_merge_keyed_new_only_when_no_old():
    df = merge_keyed(NONE, [{"well_id": "A", "n_grid": 1}])
    assert list(df["well_id"]) == ["A"]


def test_merge_keyed_reprocessed_well_wins(tmp_path):
    p = _write([{"well_id": "A", "n_grid": 1}, {"well_id": "B", "n_grid": 2}],
               tmp_path / "rec.csv")
    merged = merge_keyed(p, [{"well_id": "B", "n_grid": 22},
                             {"well_id": "C", "n_grid": 3}])
    assert set(merged["well_id"]) == {"A", "B", "C"}
    assert int(merged.loc[merged.well_id == "B", "n_grid"].iloc[0]) == 22


def test_merge_unmapped_sums_counts_across_shards(tmp_path):
    p = tmp_path / "unmapped.csv"
    merge_unmapped(NONE, [("kgs", "A", "XYZ", "m"),
                          ("kgs", "B", "XYZ", "m")]).to_csv(p, index=False)
    out = merge_unmapped(p, [("kgs", "C", "XYZ", "m"),
                             ("kgs", "D", "QQQ", "psi")])
    xyz = int(out.loc[out.raw_mnemonic == "XYZ", "count"].iloc[0])
    qqq = int(out.loc[out.raw_mnemonic == "QQQ", "count"].iloc[0])
    assert xyz == 3
    assert qqq == 1


def test_records_from_df_coerces_types(tmp_path):
    p = _write([{"well_id": "A", "n_grid": 100, "min_interval_pass": True,
                 "washout_flagged": True, "washout_interval_m": 5.0,
                 "no_bitsize": False}], tmp_path / "rec.csv")
    recs = records_from_df(pd.read_csv(p))
    assert len(recs) == 1
    r = recs[0]
    assert r.well_id == "A"
    assert isinstance(r.min_interval_pass, bool) and r.min_interval_pass is True
    assert isinstance(r.n_grid, int) and r.n_grid == 100
    assert isinstance(r.washout_interval_m, float) and r.washout_interval_m == 5.0


def test_records_from_df_passing_count(tmp_path):
    p = _write([
        {"well_id": "A", "n_grid": 1, "min_interval_pass": True,
         "washout_flagged": False, "washout_interval_m": 0.0, "no_bitsize": False},
        {"well_id": "B", "n_grid": 1, "min_interval_pass": False,
         "washout_flagged": False, "washout_interval_m": 0.0, "no_bitsize": True},
    ], tmp_path / "rec.csv")
    recs = records_from_df(pd.read_csv(p))
    assert sum(1 for r in recs if r.min_interval_pass) == 1
