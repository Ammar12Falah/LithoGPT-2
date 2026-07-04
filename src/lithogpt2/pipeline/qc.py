"""QC suite (SCHEDULED: week 2, handoff Section 4.4).

Interface is frozen now so week-1 harmonization integrates cleanly; bodies are
guarded until week 2 so nothing here can report a QC result before the code
that produces it exists. Order when implemented: null handling (done in
harmonize), physical range gates (done in harmonize), washout flagging, Hampel
spike filter, minimum usable interval (done in harmonize), deduplication.

Each function must log per-well outcomes and feed the QC dashboard PNG/HTML
that becomes the paper's data section.
"""

from __future__ import annotations

import numpy as np

from ..config import HarmonizationConfig
from .harmonize import HarmonizedWell

_WEEK2 = "Scheduled for week 2 (handoff Section 4.4); not yet implemented."


def flag_washout(
    well: HarmonizedWell,
    bit_size_in: np.ndarray | None,
    config: HarmonizationConfig,
) -> dict[str, np.ndarray]:
    """Flag washout-sensitive curves where CALI exceeds bit size by > threshold.

    Returns per-curve boolean 'suspect' masks for the curves listed in
    ``qc.washout.flag_curves``. Flagged samples are marked suspect, not
    deleted; the carbonate gate and the model consume the flags.
    """
    raise NotImplementedError(_WEEK2)


def hampel_filter(values: np.ndarray, window: int, n_sigmas: float) -> tuple[np.ndarray, float]:
    """Hampel spike filter. Returns (filtered_values, modified_fraction).

    The modified fraction per curve must be logged (YAML qc.hampel).
    """
    raise NotImplementedError(_WEEK2)


def dedup_key(well: HarmonizedWell) -> str:
    """Stable dedup hash over location + depth range + curve fingerprint.

    Catches wells present in multiple repositories (YAML qc.dedup.hash_fields).
    """
    raise NotImplementedError(_WEEK2)
