from __future__ import annotations

import math

import numpy as np

from lithogpt2.io.las import read_las
from lithogpt2.pipeline.harmonize import (
    harmonize_well,
    write_unmapped_csv,
)


def _valid(hw, curve):
    m = hw.masks[curve]
    return hw.curves[curve][m]


def test_metric_mapping_and_unmapped(config, metric_las):
    raw = read_las(metric_las, source="test")
    hw = harmonize_well(raw, config)

    # XYZ is unmapped and must be logged, not silently dropped.
    unmapped_mnems = {m for m, _u in hw.unmapped}
    assert "XYZ" in unmapped_mnems

    # Mapped canonical curves are present.
    assert "GR" in hw.present_curves
    assert "RHOB" in hw.present_curves
    assert "RDEP" in hw.present_curves
    assert "XYZ" not in hw.curves  # not a canonical curve


def test_range_gate_sets_missing_not_clipped(config, metric_las):
    raw = read_las(metric_las, source="test")
    hw = harmonize_well(raw, config)

    rhob = _valid(hw, "RHOB")
    # The 5.0 g/cc sample is out of [1.0, 3.2] and must be missing, never clipped.
    assert rhob.size >= 1
    assert np.all(rhob <= 3.2)
    assert not np.any(np.isclose(rhob, 3.2))  # not clipped to the boundary
    # Remaining density values are the in-range ones.
    assert np.all((rhob >= 2.29) & (rhob <= 2.46))


def test_null_sentinel_to_missing(config, metric_las):
    raw = read_las(metric_las, source="test")
    hw = harmonize_well(raw, config)
    gr = _valid(hw, "GR")
    # -999.25 must not survive as a value.
    assert not np.any(gr < 0)
    assert np.all((gr >= 49) & (gr <= 81))


def test_resistivity_log10(config, metric_las):
    raw = read_las(metric_las, source="test")
    hw = harmonize_well(raw, config)
    rdep = np.sort(_valid(hw, "RDEP"))
    # Original valid values 10, 20, 40, 100 -> log10.
    assert math.isclose(rdep.min(), math.log10(10), abs_tol=1e-6)
    assert math.isclose(rdep.max(), math.log10(100), abs_tol=1e-6)
    assert np.all(rdep < 3)  # all under log10(1000)


def test_unit_conversion_before_gate_imperial(config, imperial_las):
    raw = read_las(imperial_las, source="test")
    hw = harmonize_well(raw, config)

    # DEN in kg/m3 must convert to g/cc; if unconverted (2300+), the range gate
    # would drop every sample. Presence of valid RHOB proves conversion ran.
    rhob = _valid(hw, "RHOB")
    assert rhob.size >= 3
    assert np.all((rhob >= 2.29) & (rhob <= 2.51))

    # NPHI in pu must convert to v/v (15 pu -> 0.15).
    nphi = _valid(hw, "NPHI")
    assert nphi.size >= 3
    assert np.all((nphi >= 0.14) & (nphi <= 0.36))


def test_depth_converted_to_metres(config, imperial_las):
    raw = read_las(imperial_las, source="test")
    hw = harmonize_well(raw, config)
    # 500 ft -> 152.4 m; grid must live in the metric range, not feet.
    assert hw.depth_m.size >= 1
    assert 150.0 <= hw.depth_m.min() <= 153.5
    assert 150.0 <= hw.depth_m.max() <= 153.5


def test_usability_flag(config, metric_las):
    raw = read_las(metric_las, source="test")
    hw = harmonize_well(raw, config)
    # Only ~1 m of data here (< 100 m over 3 curves), so not usable.
    assert hw.usable is False


def test_write_unmapped_csv_aggregates(tmp_path):
    out = tmp_path / "unmapped.csv"
    recs = [
        ("nlog", "W1", "FOO", "unit"),
        ("nlog", "W2", "FOO", "unit"),
        ("kgs", "W3", "BAR", ""),
    ]
    write_unmapped_csv(recs, out)
    # Second call must accumulate, not overwrite.
    write_unmapped_csv([("nlog", "W9", "FOO", "unit")], out)

    text = out.read_text(encoding="utf-8").strip().splitlines()
    assert text[0] == "source,raw_mnemonic,raw_unit,count"
    rows = {tuple(line.rsplit(",", 1)[0].split(",")): int(line.rsplit(",", 1)[1]) for line in text[1:]}
    assert rows[("nlog", "FOO", "unit")] == 3
    assert rows[("kgs", "BAR", "")] == 1
