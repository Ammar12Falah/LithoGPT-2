

# --- appended: selection-heuristic + selected-file tests (rebuilt lost patch + matcher fix) ---

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
    selected: dict[str, str] = {}
    list(iter_nlog_wells(wd, "nlog", [], selected=selected))
    assert selected.get("NL-D-04") == "NL-D-04__2.las"  # the 3-curve file was chosen


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
