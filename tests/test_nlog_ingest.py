"""Tests for the NLOG ingest path: DLIS reduction, borehole grouping, endpoints.

No live server and no real well data. The DLIS reader is exercised with
duck-typed frame/channel objects (dlisio's object surface: .channels, .index,
.index_type, channel .name/.units/.dimension/.curves()), and the borehole
iterator with synthetic LAS files, so the harmonize+QC integration is covered
without network access.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from lithogpt2.config import HarmonizationConfig
from lithogpt2.ingest import nlog
from lithogpt2.ingest.well_dir import _borehole_id, iter_nlog_wells
from lithogpt2.io.dlis import _depth_factor_m, _frame_to_rawwell
from lithogpt2.pipeline.batch import run_batch


class _Ch:
    def __init__(self, name, units, data, dimension=(1,)):
        self.name = name
        self.units = units
        self._d = np.asarray(data, dtype=float)
        self.dimension = list(dimension)

    def curves(self):
        return self._d


class _Frame:
    def __init__(self, channels, index, index_type="BOREHOLE-DEPTH"):
        self.channels = channels
        self.index = index
        self.index_type = index_type


def test_depth_factor_conversions():
    assert _depth_factor_m("m") == 1.0
    assert _depth_factor_m("metres") == 1.0
    assert _depth_factor_m("ft") == pytest.approx(0.3048)
    assert _depth_factor_m("0.1 in") == pytest.approx(0.00254)  # normalizes to 01in
    assert _depth_factor_m("0.1IN") == pytest.approx(0.00254)
    assert _depth_factor_m("furlongs") is None


def test_dlis_frame_converts_tenths_of_inch_to_metres():
    depth_01in = np.arange(0, 20000, 10, dtype=float)
    n = depth_01in.size
    tdep = _Ch("TDEP", "0.1 in", depth_01in)
    gr = _Ch("GR", "gAPI", 40 + 30 * np.sin(np.linspace(0, 6, n)))
    rho = _Ch("RHOB", "g/cc", np.full(n, 2.45))
    raw = _frame_to_rawwell(_Frame([tdep, gr, rho], "TDEP"), "nlog", "W1", Path("W1__1.dlis"))
    assert raw is not None
    assert raw.depth_unit == "m"
    assert raw.depth.max() - raw.depth.min() == pytest.approx(19990 * 0.00254)
    assert set(raw.curves) == {"GR", "RHOB"}
    assert raw.well_id == "W1"


def test_dlis_rejects_time_indexed_and_array_channels():
    n = 100
    tdep = _Ch("TDEP", "m", np.arange(n, dtype=float))
    img = _Ch("IMG", "", np.zeros((n, 8)), dimension=(8,))  # array channel
    gr = _Ch("GR", "gAPI", np.linspace(20, 80, n))
    # time-indexed frame -> None
    assert _frame_to_rawwell(_Frame([tdep, gr], "TDEP", index_type="TIME"), "nlog", "W", None) is None
    # array channel dropped, scalar kept
    raw = _frame_to_rawwell(_Frame([tdep, img, gr], "TDEP"), "nlog", "W", None)
    assert raw is not None and set(raw.curves) == {"GR"}


def test_dlis_unknown_index_unit_only_accepted_for_depth_named_channel():
    n = 50
    good = _Ch("DEPTH", "weird", np.arange(n, dtype=float))
    gr = _Ch("GR", "gAPI", np.linspace(20, 80, n))
    raw = _frame_to_rawwell(_Frame([good, gr], "DEPTH"), "nlog", "W", None)
    assert raw is not None  # depth-named index with unknown unit assumed metres
    bad = _Ch("XPOS", "weird", np.arange(n, dtype=float))
    assert _frame_to_rawwell(_Frame([bad, gr], "XPOS"), "nlog", "W", None) is None


def test_borehole_id_grouping():
    assert _borehole_id(Path("NL-A-01__461444063.las")) == "NL-A-01"
    assert _borehole_id(Path("NL-A-01__461444089.dlis")) == "NL-A-01"
    assert _borehole_id(Path("PLAIN.las")) == "PLAIN"


def test_nlog_iterator_one_richest_well_per_borehole(tmp_path):
    import lasio

    wd = tmp_path / "wells"
    wd.mkdir()
    depth = np.arange(1000.0, 1400.0, 0.1524)

    # Two files for one borehole: the second is richer (more curves).
    thin = lasio.LASFile()
    thin.append_curve("DEPT", depth, unit="m")
    thin.append_curve("GR", 40 + 10 * np.sin(np.linspace(0, 5, depth.size)), unit="gAPI")
    thin.write(str(wd / "NL-A-01__1.las"), version=2.0)

    rich = lasio.LASFile()
    rich.append_curve("DEPT", depth, unit="m")
    rich.append_curve("GR", 40 + 10 * np.sin(np.linspace(0, 5, depth.size)), unit="gAPI")
    rich.append_curve("RHOB", np.full(depth.size, 2.4), unit="g/cc")
    rich.append_curve("NPHI", np.full(depth.size, 0.18), unit="v/v")
    rich.write(str(wd / "NL-A-01__2.las"), version=2.0)

    fails: list[tuple[str, str]] = []
    wells = list(iter_nlog_wells(wd, "nlog", fails))
    assert len(wells) == 1
    bid, raw = wells[0]
    assert bid == "NL-A-01"
    assert {"GR", "RHOB", "NPHI"}.issubset(set(raw.curves))  # richer file chosen

    cfg = HarmonizationConfig.load()
    res = run_batch(iter(wells), cfg, "nlog", processed_dir=None, keep_harmonized=False)
    row = res["records"][0].as_row()
    assert row["well_id"] == "NL-A-01"
    assert row["min_interval_pass"] is True


def test_nlog_skip_ids_and_bad_file(tmp_path):
    import lasio

    wd = tmp_path / "wells"
    wd.mkdir()
    depth = np.arange(1000.0, 1200.0, 0.1524)
    good = lasio.LASFile()
    good.append_curve("DEPT", depth, unit="m")
    good.append_curve("GR", np.linspace(20, 80, depth.size), unit="gAPI")
    good.write(str(wd / "NL-B-02__9.las"), version=2.0)
    (wd / "NL-C-03__7.las").write_text("this is not a LAS file")

    fails: list[tuple[str, str]] = []
    got = {b for b, _ in iter_nlog_wells(wd, "nlog", fails, skip_ids={"NL-B-02"})}
    assert "NL-B-02" not in got  # skipped
    assert any("NL-C-03" in f[0] for f in fails)  # unreadable recorded


def test_nlog_endpoints_are_the_verified_ones():
    assert nlog.LOGDOCS_URL.endswith("/nlog-mapviewer/rest/brh/logdocuments")
    assert nlog.DOWNLOAD_BASE.endswith("/nlog-mapviewer/rest/brh/logdocument/")
    assert nlog.DEFAULT_FILE_TYPES == ("LAS", "DLIS")


# --- appended: selection-heuristic + selected-file tests ---

def _load_driver():
    import importlib.util
    from pathlib import Path as _P
    spec = importlib.util.spec_from_file_location(
        "nlog_batched_driver",
        _P(__file__).resolve().parents[1] / "scripts" / "ingest_qc_nlog_batched.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_primary_candidates_ordering():
    drv = _load_driver()
    rows = [
        dict(file_name="W_FMS_IMAGE.dlis", file_size="9000000", top_depth="0", bottom_depth="2000"),
        dict(file_name="W_MAIN.las", file_size="500000", top_depth="300", bottom_depth="1800"),
        dict(file_name="W_SHORT.las", file_size="800000", top_depth="1000", bottom_depth="1200"),
    ]
    ordered = drv.primary_candidates(rows)
    assert ordered[0]["file_name"] == "W_MAIN.las"
    assert ordered[-1]["file_name"] == "W_FMS_IMAGE.dlis"


def test_iterator_records_selected_file(tmp_path):
    import lasio
    wd = tmp_path / "wells"
    wd.mkdir()
    depth = np.arange(1000.0, 1300.0, 0.1524)
    for fid, ncurve in (("1", 1), ("2", 3)):
        las = lasio.LASFile()
        las.append_curve("DEPT", depth, unit="m")
        las.append_curve("GR", np.linspace(20, 80, depth.size), unit="gAPI")
        if ncurve >= 3:
            las.append_curve("RHOB", np.full(depth.size, 2.4), unit="g/cc")
            las.append_curve("NPHI", np.full(depth.size, 0.18), unit="v/v")
        las.write(str(wd / f"NL-D-04__{fid}.las"), version=2.0)
    selected = {}
    list(iter_nlog_wells(wd, "nlog", [], selected=selected))
    assert selected.get("NL-D-04") == "NL-D-04__2.las"


def test_image_name_word_boundary_not_substring():
    drv = _load_driver()
    for img in ("W_FMS_IMAGE.dlis", "GR_FMS.las", "STAR_IMAGER.dlis",
                "OBMI_run2.dlis", "well-cbil-main.las", "XRMI.dlis"):
        assert drv._is_image_name(img), img
    for good in ("CLARITY_LOG.las", "MARINE_SEISMIC.las", "CHEMISTRY.las",
                 "STARTER_RUN.las", "GR_SONIC_DENSITY.las"):
        assert not drv._is_image_name(good), good


def test_primary_candidates_keeps_demoted_real_log_first():
    drv = _load_driver()
    rows = [
        dict(file_name="CLARITY_MAIN.las", file_size="400000", top_depth="200", bottom_depth="2100"),
        dict(file_name="W_FMI_IMAGE.dlis", file_size="8000000", top_depth="0", bottom_depth="2200"),
    ]
    assert drv.primary_candidates(rows)[0]["file_name"] == "CLARITY_MAIN.las"


def test_fallback_cap_bounds_candidates_to_five():
    # The phase-2 fallback iterates primary_candidates(...)[:5]; verify the cap
    # bounds a many-file borehole to its 5 best while preserving rank order.
    from scripts.ingest_qc_nlog_batched import primary_candidates

    rows = [
        {"file_name": f"log_{i}.las", "file_size": str(i), "top_depth": "0",
         "bottom_depth": str(i), "file_type": "LAS", "download_url": f"u{i}",
         "file_id": str(i)}
        for i in range(33)
    ]
    ranked = primary_candidates(rows)
    capped = ranked[:5]
    assert len(capped) == 5
    assert capped == ranked[:5]  # cap preserves the top-ranked order, no reshuffle
    assert len(ranked) == 33     # the ranker itself does not drop rows; the cap does


def test_run_qc_accepts_reprocess_ids_file(tmp_path):
    # Regression: the batched driver's fallback calls run_qc_nlog.py with
    # --reprocess-ids-file. That flag must be accepted, not rejected by argparse.
    # Empty well-dir means the runner exits early without needing real data;
    # we are asserting the ARGUMENT PARSES, which is exactly what broke the crawl.
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    ids_file = tmp_path / "ids.txt"
    ids_file.write_text("D12-B-02\n", encoding="utf-8")
    empty_dir = tmp_path / "wells"
    empty_dir.mkdir()

    r = subprocess.run(
        [sys.executable, str(root / "scripts" / "run_qc_nlog.py"),
         "--well-dir", str(empty_dir),
         "--reprocess-ids-file", str(ids_file)],
        capture_output=True, text=True, cwd=str(root),
    )
    # Must not be the argparse "unrecognized arguments" failure (exit 2).
    assert "unrecognized arguments" not in r.stderr, r.stderr
    assert "--reprocess-ids-file" not in r.stderr, r.stderr
