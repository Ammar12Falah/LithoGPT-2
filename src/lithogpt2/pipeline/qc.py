"""QC suite (handoff Section 4.4, WO-01 Task B).

Applied per well, in this order, each step logging what it did to a per-well QC
record:

  1. null handling   (done in harmonize; here we assert no sentinel survives)
  2. range gates      (done in harmonize; here we log fraction set missing)
  3. washout flag     CALI - BS > threshold -> suspect RHOB/NPHI/PEF
  4. Hampel spike      window 11, 4 sigma, on valid samples; log modified frac
  5. minimum interval  drop < 100 m of >= 3 canonical curves
  6. deduplication      hash(location + depth range + curve fingerprint)

Washout honors qc.washout.require_bitsize: if BS is absent for a well, flagging
is skipped, washout_flagged=false, no_bitsize=true recorded (no nominal bit
size is ever assumed). Resistivities are already log10 in the pipeline, so the
Hampel filter runs in that space. Auxiliary curves (BS) never count toward the
minimum-interval check.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

import numpy as np
from scipy.ndimage import median_filter

from ..config import HarmonizationConfig
from .harmonize import HarmonizedWell


@dataclass
class QCRecord:
    well_id: str
    source: str
    n_grid: int
    fraction_missing: dict[str, float] = field(default_factory=dict)
    washout_flagged: bool = False
    no_bitsize: bool = False
    washout_interval_m: float = 0.0
    suspect_coverage_m: dict[str, float] = field(default_factory=dict)
    hampel_modified_fraction: dict[str, float] = field(default_factory=dict)
    min_interval_pass: bool = False
    n_curves_meeting: int = 0
    drop_reason: str = ""
    dedup_hash: str = ""
    present_curves: list[str] = field(default_factory=list)

    def as_row(self) -> dict:
        row = {
            "well_id": self.well_id,
            "source": self.source,
            "n_grid": self.n_grid,
            "washout_flagged": self.washout_flagged,
            "no_bitsize": self.no_bitsize,
            "washout_interval_m": round(self.washout_interval_m, 2),
            "min_interval_pass": self.min_interval_pass,
            "n_curves_meeting": self.n_curves_meeting,
            "drop_reason": self.drop_reason,
            "dedup_hash": self.dedup_hash,
            "present": ",".join(self.present_curves),
        }
        for c, v in self.fraction_missing.items():
            row[f"missing_{c}"] = round(v, 4)
        for c, v in self.hampel_modified_fraction.items():
            row[f"hampel_{c}"] = round(v, 5)
        for c, v in self.suspect_coverage_m.items():
            row[f"suspect_m_{c}"] = round(v, 1)
        return row


def assert_no_sentinel_nulls(well: HarmonizedWell, config: HarmonizationConfig) -> None:
    """Step 1: verify harmonize already mapped null sentinels to NaN."""
    for c, arr in well.curves.items():
        finite = arr[np.isfinite(arr)]
        for nv in config.null_values:
            if np.any(np.isclose(finite, nv, atol=1e-6, rtol=0.0)):
                raise AssertionError(f"Sentinel null {nv} survived in {well.well_id}/{c}")


def fraction_missing(well: HarmonizedWell) -> dict[str, float]:
    """Step 2: per canonical curve, fraction of grid nodes that are missing."""
    n = well.depth_m.size or 1
    return {
        c: float(np.count_nonzero(~well.masks[c])) / n
        for c in well.curves
    }


def flag_washout(
    well: HarmonizedWell,
    config: HarmonizationConfig,
) -> tuple[dict[str, np.ndarray], bool, bool, float]:
    """Step 3: suspect masks for washout-sensitive curves.

    Flag samples where CALI exceeds BS by more than
    qc.washout.cali_minus_bitsize_in. Returns (suspect_masks, flagged,
    no_bitsize, washout_interval_m). If BS has no valid samples and
    require_bitsize is set, flagging is skipped (no nominal bit size assumed).
    """
    flag_curves = config.qc.washout_flag_curves
    step = well.grid_step_m
    empty = {c: np.zeros(well.depth_m.shape, dtype=bool) for c in flag_curves}

    bs = well.aux_curves.get("BS")
    bs_mask = well.aux_masks.get("BS")
    has_bs = bs is not None and bs_mask is not None and bool(np.any(bs_mask))
    if not has_bs:
        # require_bitsize: do not invent a nominal bit size.
        return empty, False, True, 0.0

    cali = well.curves.get("CALI")
    cali_mask = well.masks.get("CALI")
    if cali is None or cali_mask is None or not np.any(cali_mask):
        return empty, False, False, 0.0

    both = cali_mask & bs_mask
    threshold = config.qc.washout_cali_minus_bitsize_in
    washed = both & (cali - bs > threshold)
    washout_interval_m = float(np.count_nonzero(washed)) * step

    suspect = {}
    for c in flag_curves:
        cm = well.masks.get(c, np.zeros(well.depth_m.shape, dtype=bool))
        suspect[c] = washed & cm
    return suspect, True, False, washout_interval_m


def hampel_filter(
    values: np.ndarray, window: int = 11, n_sigmas: float = 4.0
) -> tuple[np.ndarray, float]:
    """Step 4: Hampel spike filter on valid samples. Returns (filtered, frac).

    Operates on finite samples only (NaN preserved in place). Rolling median
    and MAD via a centered window; a sample more than n_sigmas robust-sigmas
    from the local median is replaced by that median.
    """
    out = values.astype(float, copy=True)
    finite_idx = np.flatnonzero(np.isfinite(values))
    if finite_idx.size < window:
        return out, 0.0
    x = values[finite_idx].astype(float)
    med = median_filter(x, size=window, mode="nearest")
    mad = median_filter(np.abs(x - med), size=window, mode="nearest")
    sigma = 1.4826 * mad
    with np.errstate(invalid="ignore"):
        is_out = (sigma > 0) & (np.abs(x - med) > n_sigmas * sigma)
    x_filt = np.where(is_out, med, x)
    out[finite_idx] = x_filt
    frac = float(np.count_nonzero(is_out)) / float(finite_idx.size)
    return out, frac


def apply_hampel(well: HarmonizedWell, config: HarmonizationConfig) -> dict[str, float]:
    """Step 4 driver: filter every present canonical curve in place; log frac."""
    win = config.qc.hampel_window
    ns = config.qc.hampel_n_sigmas
    modified = {}
    for c in well.present_curves:
        filt, frac = hampel_filter(well.curves[c], window=win, n_sigmas=ns)
        well.curves[c] = filt
        well.masks[c] = np.isfinite(filt)
        modified[c] = frac
    return modified


def min_interval_pass(well: HarmonizedWell, config: HarmonizationConfig) -> tuple[bool, int, str]:
    """Step 5: >= min_curves canonical curves each with >= min_interval_m valid."""
    step = well.grid_step_m
    meeting = [
        c for c in well.present_curves
        if float(np.count_nonzero(well.masks[c])) * step >= config.min_interval_m
    ]
    ok = len(meeting) >= config.min_curves
    reason = "" if ok else (
        f"only {len(meeting)} curves >= {config.min_interval_m:g} m "
        f"(need {config.min_curves})"
    )
    return ok, len(meeting), reason


def dedup_key(well: HarmonizedWell) -> str:
    """Step 6: stable hash over depth range + curve fingerprint.

    Location is included when available (not present for FORCE CSV wells). The
    fingerprint is coarse so that re-uploads with minor numeric perturbations
    collide, while genuinely different wells do not.
    """
    finite = well.depth_m[np.isfinite(well.depth_m)]
    if finite.size:
        dmin, dmax = round(float(finite.min()), 1), round(float(finite.max()), 1)
    else:
        dmin = dmax = 0.0
    parts = [f"dr={dmin}:{dmax}", "curves=" + ",".join(sorted(well.present_curves))]
    # Coarse signature of each present curve: valid count + rounded mean/std.
    for c in sorted(well.present_curves):
        v = well.curves[c][well.masks[c]]
        if v.size:
            parts.append(f"{c}:{v.size}:{round(float(v.mean()), 1)}:{round(float(v.std()), 1)}")
    blob = "|".join(parts).encode("utf-8")
    return hashlib.sha1(blob).hexdigest()[:16]  # noqa: S324


def run_well_qc(well: HarmonizedWell, config: HarmonizationConfig) -> QCRecord:
    """Run steps 1 to 6 on one harmonized well and return its QC record.

    Mutates ``well`` in place for step 4 (Hampel-filtered curves). Order is the
    handoff order; washout is computed before Hampel so the suspect masks refer
    to the raw-gated signal.
    """
    assert_no_sentinel_nulls(well, config)
    rec = QCRecord(
        well_id=well.well_id,
        source=well.source,
        n_grid=int(well.depth_m.size),
        present_curves=list(well.present_curves),
    )
    rec.fraction_missing = fraction_missing(well)

    suspect, flagged, no_bs, washout_m = flag_washout(well, config)
    rec.washout_flagged = flagged
    rec.no_bitsize = no_bs
    rec.washout_interval_m = washout_m
    rec.suspect_coverage_m = {
        c: float(np.count_nonzero(m)) * well.grid_step_m for c, m in suspect.items()
    }

    rec.hampel_modified_fraction = apply_hampel(well, config)

    ok, n_meeting, reason = min_interval_pass(well, config)
    rec.min_interval_pass = ok
    rec.n_curves_meeting = n_meeting
    rec.drop_reason = reason

    rec.dedup_hash = dedup_key(well)
    return rec
