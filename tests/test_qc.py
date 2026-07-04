"""Unit tests for qc.py (WO-01 Task C)."""

from __future__ import annotations

import numpy as np

from lithogpt2.config import HarmonizationConfig
from lithogpt2.io.las import RawCurve, RawWell
from lithogpt2.pipeline.harmonize import HarmonizedWell, harmonize_well
from lithogpt2.pipeline.qc import (
    dedup_key,
    flag_washout,
    hampel_filter,
    min_interval_pass,
    run_well_qc,
)

STEP = 0.1524
CFG = HarmonizationConfig.load()


def _grid(n, start_k=1000):
    return np.array([STEP * (start_k + i) for i in range(n)], dtype=float)


def _well(n, curve_valid, cali=None, bs=None):
    """Build a HarmonizedWell with given per-curve valid-sample counts."""
    depth = _grid(n)
    curves, masks = {}, {}
    for c in CFG.canonical_curves:
        arr = np.full(n, np.nan)
        k = curve_valid.get(c, 0)
        arr[:k] = 1.0
        curves[c] = arr
        masks[c] = np.isfinite(arr)
    if cali is not None:
        curves["CALI"] = cali
        masks["CALI"] = np.isfinite(cali)
    aux_curves, aux_masks = {}, {}
    for a in CFG.auxiliary_curves():
        arr = np.full(n, np.nan)
        aux_curves[a] = arr
        aux_masks[a] = np.isfinite(arr)
    if bs is not None:
        aux_curves["BS"] = bs
        aux_masks["BS"] = np.isfinite(bs)
    present = [c for c in CFG.canonical_curves if np.any(masks[c])]
    return HarmonizedWell(
        well_id="T", source="test", depth_m=depth, grid_step_m=STEP,
        curves=curves, masks=masks, aux_curves=aux_curves, aux_masks=aux_masks,
        present_curves=present, usable=True,
    )


# --- Range gate boundary (in harmonize) ------------------------------------
def test_range_gate_boundary():
    depth = _grid(3)
    raw = RawWell(
        well_id="R", source="test", depth=depth, depth_unit="m",
        curves={"GR": RawCurve("GR", "gAPI", np.array([399.9, 400.1, 50.0]))},
    )
    hw = harmonize_well(raw, CFG)
    # 399.9 just inside [0,400] stays; 400.1 just outside -> missing; 50 stays.
    assert hw.masks["GR"][0]
    assert not hw.masks["GR"][1]
    assert hw.masks["GR"][2]


# --- Washout: BS present and BS absent -------------------------------------
def test_washout_with_bs():
    n = 20
    cali = np.full(n, 12.0)
    bs = np.full(n, 12.0)
    cali[5:10] = 15.5  # 3.5 in over bit size, above the 2.0 threshold
    well = _well(n, {"RHOB": n, "NPHI": n, "PEF": n}, cali=cali, bs=bs)
    suspect, flagged, no_bs, washout_m = flag_washout(well, CFG)
    assert flagged and not no_bs
    assert np.count_nonzero(suspect["RHOB"]) == 5
    assert washout_m > 0


def test_washout_no_bs():
    n = 20
    cali = np.full(n, 15.0)
    well = _well(n, {"RHOB": n, "NPHI": n, "PEF": n}, cali=cali, bs=None)
    suspect, flagged, no_bs, washout_m = flag_washout(well, CFG)
    assert not flagged and no_bs
    assert washout_m == 0.0
    assert np.count_nonzero(suspect["RHOB"]) == 0


# --- Hampel on a synthetic spike -------------------------------------------
def test_hampel_removes_spike():
    rng = np.random.default_rng(1)
    x = rng.normal(50.0, 1.0, 200)  # realistic noisy baseline (MAD > 0)
    x[100] = 5000.0  # single gross spike
    filt, frac = hampel_filter(x, window=11, n_sigmas=4.0)
    assert filt[100] < 100.0  # spike pulled back toward the local median
    assert frac > 0.0


# --- Minimum interval boundary ---------------------------------------------
def test_min_interval_just_above_and_below():
    per_100m = int(np.ceil(CFG.min_interval_m / STEP)) + 1  # ~657 samples = 100.1 m
    n = per_100m + 5
    above = _well(n, {"GR": per_100m, "RHOB": per_100m, "DTC": per_100m})
    ok, meeting, _ = min_interval_pass(above, CFG)
    assert ok and meeting >= CFG.min_curves

    short = per_100m - 20  # < 100 m
    below = _well(n, {"GR": per_100m, "RHOB": per_100m, "DTC": short})
    ok2, meeting2, reason = min_interval_pass(below, CFG)
    assert not ok2 and meeting2 == 2 and "curves" in reason


# --- Dedup: identical, near-identical, different ----------------------------
def test_dedup_identical_and_near_and_different():
    rng = np.random.default_rng(0)
    n = 700
    base = _well(n, {"GR": n, "RHOB": n, "DTC": n})
    base.curves["GR"][:] = rng.normal(60, 5, n)

    identical = _well(n, {"GR": n, "RHOB": n, "DTC": n})
    identical.curves["GR"][:] = base.curves["GR"]

    near = _well(n, {"GR": n, "RHOB": n, "DTC": n})
    near.curves["GR"][:] = base.curves["GR"] + rng.normal(0, 0.001, n)

    different = _well(n, {"GR": n, "RHOB": n, "DTC": n})
    different.curves["GR"][:] = rng.normal(120, 30, n)

    assert dedup_key(base) == dedup_key(identical)
    assert dedup_key(base) == dedup_key(near)      # coarse fingerprint collides
    assert dedup_key(base) != dedup_key(different)


# --- Integration: run_well_qc end to end on a synthetic harmonized well -----
def test_run_well_qc_record():
    n = 700
    cali = np.full(n, 12.0)
    bs = np.full(n, 12.0)
    cali[100:200] = 15.0
    well = _well(n, {"GR": n, "RHOB": n, "DTC": n, "NPHI": n, "PEF": n}, cali=cali, bs=bs)
    rec = run_well_qc(well, CFG)
    assert rec.min_interval_pass
    assert rec.washout_flagged and not rec.no_bitsize
    assert rec.dedup_hash
    row = rec.as_row()
    assert row["well_id"] == "T" and "hampel_GR" in row
