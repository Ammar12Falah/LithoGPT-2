"""Unit tests for the incremental resume/merge helpers (pure pandas)."""

from pathlib import Path

import pandas as pd

from lithogpt2.pipeline.incremental import (
    done_well_ids,
    merge_keyed,
    merge_unmapped,
    records_from_df,
)


def _write_csv(path: Path, rows: list[dict]) -> Path:
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def test_done_well_ids_empty_when_missing(tmp_path):
    assert done_well_ids(tmp_path / "nope.csv") == set()


def test_done_well_ids_reads_ids(tmp_path):
    p = _write_csv(tmp_path / "rec.csv", [{"well_id": "A"}, {"well_id": "B"}])
    assert done_well_ids(p) == {"A", "B"}


def test_merge_keyed_new_only_when_no_old():
    out = merge_keyed(Path("does_not_exist.csv"), [{"well_id": "A", "v": 1}])
    assert list(out["well_id"]) == ["A"]


def test_merge_keyed_reprocessed_well_wins(tmp_path):
    old = _write_csv(tmp_path / "rec.csv", [{"well_id": "A", "v": 1}, {"well_id": "B", "v": 2}])
    out = merge_keyed(old, [{"well_id": "A", "v": 99}])
    vals = dict(zip(out["well_id"], out["v"]))
    assert vals["A"] == 99 and vals["B"] == 2


def test_merge_unmapped_sums_counts_across_shards(tmp_path):
    old = _write_csv(
        tmp_path / "un.csv",
        [{"source": "kgs", "raw_mnemonic": "X", "raw_unit": "IN", "count": 3}],
    )
    out = merge_unmapped(old, [("kgs", "X", "IN"), ("kgs", "X", "IN"), ("kgs", "Y", "")])
    rows = {(r.raw_mnemonic, r.raw_unit): r.count for r in out.itertuples()}
    assert rows[("X", "IN")] == 5
    assert rows[("Y", "")] == 1


def test_records_from_df_coerces_types(tmp_path):
    p = _write_csv(
        tmp_path / "rec.csv",
        [{"well_id": "A", "source": "kgs", "min_interval_pass": "True", "n_grid": "10"}],
    )
    df = pd.read_csv(p)
    recs = records_from_df(df)
    assert recs[0].well_id == "A"


def test_records_from_df_passing_count(tmp_path):
    p = _write_csv(
        tmp_path / "rec.csv",
        [
            {"well_id": "A", "min_interval_pass": True},
            {"well_id": "B", "min_interval_pass": False},
        ],
    )
    df = pd.read_csv(p)
    recs = records_from_df(df)
    assert sum(1 for r in recs if r.min_interval_pass) == 1


def test_empty_csv_treated_as_no_data(tmp_path):
    p = tmp_path / "empty.csv"
    p.write_text("")
    assert done_well_ids(p) == set()
    out = merge_keyed(p, [{"well_id": "A", "v": 1}])
    assert list(out["well_id"]) == ["A"]
