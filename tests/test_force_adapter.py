"""Offline unit test for the FORCE CSV to RawWell adapter."""

from __future__ import annotations

import numpy as np

from lithogpt2.ingest.force2020 import iter_force_wells


def test_iter_force_wells(tmp_path):
    csv = tmp_path / "mini_train.csv"
    csv.write_text(
        "WELL;DEPTH_MD;GR;RHOB;ROP;FORCE_2020_LITHOFACIES_LITHOLOGY\n"
        "15/9-13;100.0;45.1;2.30;12.0;65000\n"
        "15/9-13;100.15;46.0;2.31;12.5;65000\n"
        "16/1-2;200.0;60.2;2.45;;30000\n"
        "16/1-2;200.15;61.0;2.46;8.0;30000\n",
        encoding="utf-8",
    )
    wells = list(iter_force_wells(str(csv)))
    assert [w for w, _ in wells] == ["15/9-13", "16/1-2"]

    _, first = wells[0]
    assert first.source == "force2020"
    assert first.depth_unit == "m"
    np.testing.assert_allclose(first.depth, [100.0, 100.15])
    # GR and RHOB are curves; the two admin/label columns are not.
    assert "GR" in first.curves and "RHOB" in first.curves
    assert "FORCE_2020_LITHOFACIES_LITHOLOGY" not in first.curves
    assert first.curves["RHOB"].unit == "g/cm3"


def test_iter_force_wells_max(tmp_path):
    csv = tmp_path / "mini2.csv"
    csv.write_text(
        "WELL;DEPTH_MD;GR\nA;1.0;10\nA;1.15;11\nB;2.0;20\nC;3.0;30\n",
        encoding="utf-8",
    )
    wells = list(iter_force_wells(str(csv), max_wells=2))
    assert [w for w, _ in wells] == ["A", "B"]
