import numpy as np

from lithogpt2.pipeline.harmonize import _null_rail_pileup


def test_rail_pileup_nulled_high():
    v = np.concatenate([np.linspace(1.0, 4.0, 200), np.full(60, 5.0)])  # 60 welded to hi=5.0
    out, n = _null_rail_pileup(v.copy(), 0.01, 5.0)
    assert n == 60
    assert np.isnan(out[-60:]).all()
    assert np.isfinite(out[:200]).all()

def test_midrange_mode_preserved():
    # RHOB-like: heavy mode at 2.55, bounds 1.0..3.2 -> must NOT be nulled
    v = np.concatenate([np.full(120, 2.55), np.linspace(1.5, 3.0, 200)])
    out, n = _null_rail_pileup(v.copy(), 1.0, 3.2)
    assert n == 0
    assert np.isfinite(out).all()

def test_small_mass_below_frac_ignored():
    v = np.concatenate([np.linspace(1.0, 4.0, 990), np.full(10, 5.0)])  # 1% < 5%
    out, n = _null_rail_pileup(v.copy(), 0.01, 5.0)
    assert n == 0
