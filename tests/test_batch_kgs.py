"""Offline tests for the KGS LAS path and the shared batch engine."""

from __future__ import annotations

from pathlib import Path

from lithogpt2.config import HarmonizationConfig
from lithogpt2.ingest import las_dir
from lithogpt2.ingest.las_dir import iter_las_wells
from lithogpt2.pipeline.batch import merged_pass_count, run_batch, write_source_reports

CFG = HarmonizationConfig.load()

# Two grid-aligned synthetic LAS wells (imperial depth to exercise ft->m).
LAS_A = """~Version
 VERS. 2.0 :
 WRAP. NO :
~Well
 STRT.FT 500.0 :
 STOP.FT 502.0 :
 STEP.FT 0.5 :
 NULL. -999.25 :
 WELL. KGS_A :
~Curve
 DEPT.FT :
 GR.gAPI :
 RHOB.g/cc :
 NPHI.v/v :
 CALI.in :
 BS.in :
~ASCII
500.0 50.0 2.30 0.20 12.0 12.0
500.5 55.0 2.35 0.22 15.0 12.0
501.0 60.0 2.40 0.24 12.5 12.0
501.5 65.0 2.45 0.26 12.0 12.0
502.0 70.0 2.50 0.28 12.0 12.0
"""

LAS_B = LAS_A.replace("KGS_A", "KGS_B")


def _make_dir(tmp_path: Path) -> Path:
    d = tmp_path / "las"
    d.mkdir()
    (d / "kgs_a.las").write_text(LAS_A, encoding="utf-8")
    (d / "kgs_b.las").write_text(LAS_B, encoding="utf-8")
    return d


def test_iter_las_wells_reads_two(tmp_path):
    d = _make_dir(tmp_path)
    failures: list = []
    wells = list(iter_las_wells(d, "kgs", failures))
    assert [w for w, _ in wells] == ["kgs_a", "kgs_b"]
    assert not failures
    _, raw = wells[0]
    assert raw.source == "kgs"
    assert "GR" in raw.curves


def test_iter_las_wells_records_failure(tmp_path, monkeypatch):
    d = _make_dir(tmp_path)

    def boom(path, source, well_id=None):
        if "kgs_a" in str(path):
            raise ValueError("corrupt LAS")
        from lithogpt2.io.las import read_las as real
        return real(path, source, well_id)

    monkeypatch.setattr(las_dir, "read_las", boom)
    failures: list = []
    wells = list(iter_las_wells(d, "kgs", failures))
    assert [w for w, _ in wells] == ["kgs_b"]  # the good one still comes through
    assert failures and failures[0][0] == "kgs_a" and "corrupt" in failures[0][1]


def test_iter_las_wells_max(tmp_path):
    d = _make_dir(tmp_path)
    wells = list(iter_las_wells(d, "kgs", [], max_wells=1))
    assert len(wells) == 1


def test_run_batch_end_to_end(tmp_path):
    d = _make_dir(tmp_path)
    wells = iter_las_wells(d, "kgs", [])
    result = run_batch(wells, CFG, "kgs", processed_dir=tmp_path / "proc")
    assert len(result["records"]) == 2
    assert not result["failures"]
    assert (tmp_path / "proc" / "kgs_a.parquet").exists()
    paths = write_source_reports(result, "kgs", tmp_path / "reports")
    assert paths["records"].exists() and paths["coverage"].exists()


def test_merged_pass_count():
    from lithogpt2.pipeline.qc import QCRecord

    def rec(passed):
        r = QCRecord(well_id="x", source="s", n_grid=10)
        r.min_interval_pass = passed
        return r

    by_source = {
        "force2020": [rec(True), rec(True), rec(False)],
        "kgs": [rec(True), rec(True)],
    }
    out = merged_pass_count(by_source)
    assert out["total_wells"] == 5
    assert out["total_passing"] == 4
    assert out["per_source"]["force2020"]["qc_passing"] == 2
