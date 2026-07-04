"""Physics prior and carbonate gating (SCHEDULED: weeks 3-4, handoff Section 5).

Interface frozen now; bodies guarded until weeks 3-4. The three-way ablation
(prior-off, prior-on-ungated, prior-on-gated) is the paper's spine, so the
gate must be validated against FORCE 2020 lithofacies labels and its
precision/recall reported before the test manifest is frozen at Gate G2.

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
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..config import HarmonizationConfig
from .harmonize import HarmonizedWell

_WEEKS34 = "Scheduled for weeks 3-4 (handoff Section 5); not yet implemented."


@dataclass(frozen=True)
class AthyTrend:
    phi0: float
    lambda_m: float
    basin_group: str


def fit_athy_trend(
    tvd_m: np.ndarray,
    porosity_like: np.ndarray,
    basin_group: str,
) -> AthyTrend:
    """Fit a constrained Athy compaction trend per basin group (Huber loss)."""
    raise NotImplementedError(_WEEKS34)


def carbonate_gate(
    well: HarmonizedWell,
    washout_masks: dict[str, np.ndarray],
    config: HarmonizationConfig,
) -> np.ndarray:
    """Return the prior_confidence channel (0 in carbonate/invalid intervals)."""
    raise NotImplementedError(_WEEKS34)
