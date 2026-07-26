"""Physics prior and carbonate gating (R9, ATCE Phase 7, implemented 2026-07-26).

Athy-form compaction trend fitted per basin group with Huber loss:
    phi(z) = phi0 * exp(-z / lambda),  phi0 in [0.2, 0.7], lambda in [500, 5000] m.
Density trend from porosity via matrix/fluid mixing (2.65 / 1.0 g/cc); sonic
trend via a documented RHG-style transform.

Gating: an interval bypasses the prior (prior_confidence = 0) when any hold:
  - PEF >= pef_carbonate_threshold on washout-clean samples;
  - PEF absent and a carbonate heuristic fires (RHOB > 2.6 and GR < 40 over
    >= 10 m);
  - post-fit rolling residual z-score > residual_variance_gate_z for > 20 m.
Elsewhere prior_confidence = 1. The model consumes residuals where confidence
is 1 and raw normalized values where 0, with prior_confidence as an input
channel; generation adds the trend back where it was applied.

Implementation note (R9, this commit): `carbonate_gate`'s third condition
(post-fit residual z-score) needs a fitted AthyTrend to compute residuals
against, which the original frozen signature does not carry. Extended with an
OPTIONAL `fitted_trend` keyword (default None) rather than changing the
positional signature -- existing callers with (well, washout_masks, config)
still work (conditions 1-2 only); passing fitted_trend enables condition 3.
This is a minimal, backward-compatible extension, not a silent interface
break.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import least_squares

from ..config import HarmonizationConfig
from .harmonize import HarmonizedWell

# Literature-plausible Athy-law bounds (already pinned in the frozen docstring
# above; not re-derived here).
PHI0_BOUNDS = (0.2, 0.7)
LAMBDA_BOUNDS_M = (500.0, 5000.0)
HUBER_DELTA = 0.03  # residual scale (porosity fraction units) at which Huber loss transitions

# Matrix/fluid densities for the density-from-porosity mixing law (g/cc).
RHO_MATRIX = 2.65
RHO_FLUID = 1.0

# Carbonate heuristic (RHOB, GR) sustained-interval thresholds.
CARBONATE_RHOB_MIN = 2.6
CARBONATE_GR_MAX = 40.0
CARBONATE_HEURISTIC_MIN_RUN_M = 10.0
RESIDUAL_GATE_MIN_RUN_M = 20.0


@dataclass(frozen=True)
class AthyTrend:
    phi0: float
    lambda_m: float
    basin_group: str


def _athy(z: np.ndarray, phi0: float, lambda_m: float) -> np.ndarray:
    return phi0 * np.exp(-z / lambda_m)


def fit_athy_trend(
    tvd_m: np.ndarray,
    porosity_like: np.ndarray,
    basin_group: str,
) -> AthyTrend:
    """Fit a constrained Athy compaction trend per basin group (Huber loss).

    tvd_m, porosity_like must be finite and same length (caller filters NaN/
    mask first; this function asserts finiteness rather than silently
    dropping, since a silent drop here would change which train rows fit the
    trend without it being visible to the caller).
    """
    z = np.asarray(tvd_m, dtype=np.float64)
    phi = np.asarray(porosity_like, dtype=np.float64)
    if z.shape != phi.shape:
        raise ValueError(f"tvd_m shape {z.shape} != porosity_like shape {phi.shape}")
    if not (np.isfinite(z).all() and np.isfinite(phi).all()):
        raise ValueError(
            "fit_athy_trend requires finite inputs; filter NaN/invalid rows before calling"
        )
    if z.size < 10:
        raise ValueError(f"fit_athy_trend needs >=10 samples, got {z.size}")

    def residuals(params):
        phi0, lambda_m = params
        return _athy(z, phi0, lambda_m) - phi

    x0 = np.array([0.5 * sum(PHI0_BOUNDS), 0.5 * sum(LAMBDA_BOUNDS_M)])
    lower = np.array([PHI0_BOUNDS[0], LAMBDA_BOUNDS_M[0]])
    upper = np.array([PHI0_BOUNDS[1], LAMBDA_BOUNDS_M[1]])

    result = least_squares(
        residuals, x0, bounds=(lower, upper), loss="huber", f_scale=HUBER_DELTA,
        method="trf",
    )
    phi0_fit, lambda_fit = result.x
    return AthyTrend(phi0=float(phi0_fit), lambda_m=float(lambda_fit), basin_group=basin_group)


def density_from_porosity(phi: np.ndarray) -> np.ndarray:
    """Matrix/fluid mixing law: rho = phi*rho_fluid + (1-phi)*rho_matrix."""
    phi = np.asarray(phi, dtype=np.float64)
    return phi * RHO_FLUID + (1.0 - phi) * RHO_MATRIX


def sonic_from_porosity(phi: np.ndarray, dtc_matrix_us_ft: float = 55.5,
                         dtc_fluid_us_ft: float = 189.0) -> np.ndarray:
    """Raymer-Hunt-Gardner (RHG) transit-time transform: a documented,
    widely-used alternative to Wyllie's time-average equation, preferred for
    unconsolidated/high-porosity sections (matches the docstring's
    'documented RHG-style transform').

    DT = DT_matrix * (1 - phi)^2 + DT_fluid * phi   (RHG approximation form)
    """
    phi = np.asarray(phi, dtype=np.float64)
    return dtc_matrix_us_ft * (1.0 - phi) ** 2 + dtc_fluid_us_ft * phi


def _rolling_zscore(residual: np.ndarray, window_samples: int) -> np.ndarray:
    """Centered rolling z-score of `residual` over `window_samples`. NaNs in
    the input propagate to NaN output (never silently coerced to 0)."""
    n = len(residual)
    z = np.full(n, np.nan)
    half = window_samples // 2
    for i in range(n):
        lo = max(0, i - half)
        hi = min(n, i + half + 1)
        window = residual[lo:hi]
        window = window[np.isfinite(window)]
        if len(window) < max(3, window_samples // 4):
            continue
        mu = window.mean()
        sd = window.std()
        if sd < 1e-9:
            z[i] = 0.0
        else:
            z[i] = (residual[i] - mu) / sd if np.isfinite(residual[i]) else np.nan
    return z


def _sustained_run_mask(condition: np.ndarray, min_run_samples: int) -> np.ndarray:
    """True only where `condition` holds for a contiguous run of at least
    min_run_samples (matches the docstring's 'over >= N m' / 'for > N m'
    sustained-interval language, not a pointwise trigger)."""
    out = np.zeros_like(condition, dtype=bool)
    n = len(condition)
    i = 0
    while i < n:
        if not condition[i]:
            i += 1
            continue
        j = i
        while j < n and condition[j]:
            j += 1
        if (j - i) >= min_run_samples:
            out[i:j] = True
        i = j
    return out


def carbonate_gate(
    well: HarmonizedWell,
    washout_masks: dict[str, np.ndarray],
    config: HarmonizationConfig,
    fitted_trend: AthyTrend | None = None,
    trend_curve_name: str = "NPHI",
) -> np.ndarray:
    """Return the prior_confidence channel (0 in carbonate/invalid intervals).

    Conditions 1-2 (PEF threshold, RHOB/GR heuristic) run with just
    (well, washout_masks, config). Condition 3 (post-fit residual z-score)
    additionally needs `fitted_trend` -- the AthyTrend for this well's basin
    group -- since it requires the trend residual. If fitted_trend is None,
    condition 3 is skipped and the gate reports only conditions 1-2 (a
    documented partial gate, not a silent omission).
    """
    n = len(well.depth_m)
    confidence = np.ones(n, dtype=np.float64)
    grid_step = well.grid_step_m

    pef = well.curves.get("PEF")
    pef_mask = well.masks.get("PEF")
    rhob = well.curves.get("RHOB")
    rhob_mask = well.masks.get("RHOB")
    gr = well.curves.get("GR")
    gr_mask = well.masks.get("GR")

    pg = config.prior_gate

    # Condition 1: PEF >= threshold on washout-clean samples.
    if pef is not None and pef_mask is not None:
        clean = washout_masks.get("PEF", np.ones(n, dtype=bool))
        cond1 = (pef >= pg.pef_carbonate_threshold) & pef_mask & clean
        confidence[cond1] = 0.0

    # Condition 2: PEF absent + carbonate heuristic sustained >= 10 m.
    pef_present_frac = float(pef_mask.mean()) if pef_mask is not None else 0.0
    if pef is None or pef_present_frac < 0.5:
        if rhob is not None and gr is not None and rhob_mask is not None and gr_mask is not None:
            both_valid = rhob_mask & gr_mask
            heuristic = (rhob > CARBONATE_RHOB_MIN) & (gr < CARBONATE_GR_MAX) & both_valid
            min_run = max(1, int(round(CARBONATE_HEURISTIC_MIN_RUN_M / grid_step)))
            sustained = _sustained_run_mask(heuristic, min_run)
            confidence[sustained] = 0.0

    # Condition 3: post-fit rolling residual z-score > gate_z for > 20 m.
    if fitted_trend is not None:
        curve = well.curves.get(trend_curve_name)
        curve_mask = well.masks.get(trend_curve_name)
        if curve is not None and curve_mask is not None:
            pred = _athy(well.depth_m, fitted_trend.phi0, fitted_trend.lambda_m)
            residual = np.where(curve_mask, curve - pred, np.nan)
            window_samples = max(5, int(round(RESIDUAL_GATE_MIN_RUN_M / grid_step)))
            z = _rolling_zscore(residual, window_samples)
            over = np.nan_to_num(np.abs(z), nan=0.0) > pg.residual_variance_gate_z
            min_run = max(1, int(round(RESIDUAL_GATE_MIN_RUN_M / grid_step)))
            sustained = _sustained_run_mask(over, min_run)
            confidence[sustained] = 0.0

    return confidence
