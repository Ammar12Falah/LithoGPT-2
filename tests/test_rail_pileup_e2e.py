"""End-to-end coverage of the rail-null on the REAL _process_channel path.

The existing unit tests call _null_rail_pileup in isolation with log-space bounds
(hi=5.0) that the production resistivity path never sees. Production runs the rail
null in linear pre-transform space (bounds 0.01..100000) and logs afterward. These
tests exercise that real sequence: null -> convert -> gate -> rail -> log10 -> resample.
"""
import numpy as np

from lithogpt2.pipeline.harmonize import _process_channel


def _grid(n, step=0.1524, start=1000.0):
    return start + step * np.arange(n, dtype=float)


def test_resistivity_ceiling_fill_nulled_end_to_end():
    # 240 continuous real readings (10..5000 ohmm) + 60 welded to the 100000 ceiling.
    grid = _grid(300)
    depth = grid.copy()                      # raw depths ON grid nodes
    real = np.linspace(10.0, 5000.0, 240)
    fill = np.full(60, 100000.0)             # linear valid_range hi
    raw = np.concatenate([real, fill])
    out, note = _process_channel(
        raw, "ohm.m", {}, "ohm.m", (0.01, 100000.0), "log10",
        depth, grid, 0.08, (-999.25,), "RSHA",
    )
    # the 60 ceiling samples must be missing after the rail null (not log10(100000)=5.0)
    assert not np.any(np.isclose(out[np.isfinite(out)], 5.0, atol=1e-6)), \
        "ceiling fill survived as log10(1e5)=5.0"
    # real data survived and was log-transformed: log10(10..5000) = 1.0 .. ~3.7
    fin = out[np.isfinite(out)]
    assert fin.size >= 200
    assert fin.min() >= 0.9 and fin.max() <= 3.8


def test_midrange_density_mode_survives_end_to_end():
    # RHOB-like: heavy mode at 2.55 (mid-range, bounds 1.0..3.2), transform none.
    grid = _grid(300)
    depth = grid.copy()
    mode = np.full(120, 2.55)
    spread = np.linspace(1.6, 3.0, 180)
    raw = np.concatenate([mode, spread])
    out, note = _process_channel(
        raw, "g/cc", {}, "g/cc", (1.0, 3.2), "none",
        depth, grid, 0.08, (-999.25,), "RHOB",
    )
    # the 2.55 mode is mid-range -> untouched; it must still be present
    assert np.any(np.isclose(out[np.isfinite(out)], 2.55, atol=1e-6)), \
        "real mid-range density mode was wrongly nulled"


def test_lower_rail_fill_nulled_end_to_end():
    # mass welded to the LOWER bound 0.01 -> should also null (rule is bound-keyed).
    grid = _grid(300)
    depth = grid.copy()
    real = np.linspace(5.0, 500.0, 240)
    fill = np.full(60, 0.01)
    raw = np.concatenate([real, fill])
    out, note = _process_channel(
        raw, "ohm.m", {}, "ohm.m", (0.01, 100000.0), "log10",
        depth, grid, 0.08, (-999.25,), "RMED",
    )
    # log10(0.01) = -2.0 must not survive as a mass
    survivors = out[np.isfinite(out)]
    assert np.count_nonzero(np.isclose(survivors, -2.0, atol=1e-6)) < 5
