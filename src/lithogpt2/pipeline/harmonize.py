"""Harmonization: raw LAS wells to a canonical, gridded representation.

Order of operations (handoff Section 4.3, YAML header):
  1. Resolve raw mnemonics to canonical curves. Unmapped mnemonics are logged
     to reports/unmapped_mnemonics.csv, never silently dropped.
  2. Replace declared null sentinels with NaN.
  3. Apply unit conversions (multiplicative), *before* range gates.
  4. Range-gate: out-of-range samples become missing (NaN), never clipped.
  5. Transform: log10 for resistivities.
  6. Resample every curve onto the fixed 0.1524 m depth grid.
  7. Emit one value array plus one boolean present/valid mask per canonical
     curve, and a usability decision.

What this module does NOT do (by design, later weeks / other modules):
  - Normalization statistics are computed on the *training split only* at
    dataset-build time (:func:`compute_norm_stats`), not per well here.
  - Washout, Hampel spike filtering, dedup live in qc.py (week 2).
  - The physics prior and gating live in trend.py (weeks 3-4).

Resampling policy (v1, documented for advisor review):
  Nearest-sample-within-tolerance (tolerance = half a grid step). This never
  interpolates a value across a data gap, so curves sampled coarser than the
  grid will contain NaNs between samples. That is the honest behaviour; it
  refuses to invent samples. Revisit at G1 if coverage suffers.
"""

from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from ..config import HarmonizationConfig
from ..io.las import RawWell

_NULL_ATOL = 1e-3  # tolerance for matching declared null sentinels


@dataclass
class HarmonizedWell:
    well_id: str
    source: str
    depth_m: np.ndarray
    grid_step_m: float
    curves: dict[str, np.ndarray]  # canonical -> float array, NaN = missing
    masks: dict[str, np.ndarray]  # canonical -> bool array, True = valid
    aux_curves: dict[str, np.ndarray] = field(default_factory=dict)  # QC-only (e.g. BS)
    aux_masks: dict[str, np.ndarray] = field(default_factory=dict)
    present_curves: list[str] = field(default_factory=list)
    usable: bool = False
    # (raw_mnemonic, raw_unit) pairs seen in this well that had no mapping.
    unmapped: list[tuple[str, str]] = field(default_factory=list)
    unit_notes: list[str] = field(default_factory=list)

    def curve_coverage_m(self, canonical: str) -> float:
        """Valid thickness for a curve = valid-sample count times grid step."""
        return float(np.count_nonzero(self.masks[canonical])) * self.grid_step_m


def _normalize_unit(u: str) -> str:
    return u.strip().lower().replace(" ", "").replace(".", "").replace("_", "")


def _build_grid(depth_m: np.ndarray, step: float) -> np.ndarray:
    finite = depth_m[np.isfinite(depth_m)]
    if finite.size == 0:
        return np.empty(0, dtype=float)
    dmin, dmax = float(np.min(finite)), float(np.max(finite))
    first = np.ceil(dmin / step) * step
    last = np.floor(dmax / step) * step
    if last < first:
        return np.empty(0, dtype=float)
    n = int(round((last - first) / step)) + 1
    return first + step * np.arange(n, dtype=float)


def _resample_nearest(
    raw_depth: np.ndarray,
    raw_values: np.ndarray,
    grid: np.ndarray,
    tol: float,
) -> np.ndarray:
    """Nearest raw sample within ``tol`` of each grid node, else NaN."""
    out = np.full(grid.shape, np.nan, dtype=float)
    valid = np.isfinite(raw_depth) & np.isfinite(raw_values)
    if not np.any(valid) or grid.size == 0:
        return out
    rd = raw_depth[valid]
    rv = raw_values[valid]
    order = np.argsort(rd)
    rd = rd[order]
    rv = rv[order]

    idx = np.searchsorted(rd, grid)
    for i, node in enumerate(grid):
        best_j = -1
        best_d = tol
        for j in (idx[i] - 1, idx[i]):
            if 0 <= j < rd.size:
                d = abs(rd[j] - node)
                if d <= best_d:
                    best_d = d
                    best_j = j
        if best_j >= 0:
            out[i] = rv[best_j]
    return out


def _to_missing_nulls(values: np.ndarray, null_values: tuple[float, ...]) -> np.ndarray:
    out = values.astype(float, copy=True)
    for nv in null_values:
        out[np.isclose(out, nv, atol=_NULL_ATOL, rtol=0.0)] = np.nan
    return out



_RAIL_EPS = 1e-6        # closeness to a valid_range bound
_RAIL_MIN_FRAC = 0.05     # a value must hold >=5% of finite samples to count as a discrete mass
_RAIL_MIN_COUNT = 25      # and at least this many samples, so tiny wells don't false-trigger

def _null_rail_pileup(values, lo, hi):
    """Null discrete masses welded to a valid_range rail (off-scale fill sentinels).

    A value is nulled only if it (a) equals a range bound within _RAIL_EPS and
    (b) is held by a large, discrete fraction of finite samples. Mid-range modes
    (real rock modes like RHOB density) are never near a bound, so they are exempt.
    Sets to missing (NaN); never clips. Returns (values, nulled_count).
    """
    import numpy as _np
    v = values
    finite = _np.isfinite(v)
    n = int(finite.sum())
    if n == 0:
        return values, 0
    nulled = 0
    for bound in (lo, hi):
        on_rail = finite & (_np.abs(v - bound) <= _RAIL_EPS)
        c = int(on_rail.sum())
        if c >= _RAIL_MIN_COUNT and (c / n) >= _RAIL_MIN_FRAC:
            v = _np.where(on_rail, _np.nan, v)
            nulled += c
    return v, nulled


def _process_channel(
    raw_values: np.ndarray,
    raw_unit: str,
    convert: dict[str, float],
    canon_unit: str,
    valid_range: tuple[float, float],
    transform: str,
    depth_m: np.ndarray,
    grid: np.ndarray,
    tol: float,
    null_values: tuple[float, ...],
    label: str,
) -> tuple[np.ndarray, str | None]:
    """Null -> convert -> range-gate -> transform -> resample. One channel.

    Returns the resampled grid array and an optional unit note. Unit conversion
    is applied before the range gate; out-of-range samples go to missing (never
    clipped); the transform (log10 or none) runs after gating.
    """
    note: str | None = None
    values = _to_missing_nulls(np.asarray(raw_values, dtype=float), null_values)

    ru = _normalize_unit(raw_unit)
    conv = {_normalize_unit(k): v for k, v in convert.items()}
    cu = _normalize_unit(canon_unit)
    if ru in conv:
        values = values * conv[ru]
    elif ru in ("", cu):
        pass
    else:
        note = f"{label}: unrecognized unit {raw_unit!r} (expected {canon_unit!r}); assumed native"

    lo, hi = valid_range
    values = np.where((values < lo) | (values > hi), np.nan, values)
    # sentinel rail pileup -> missing (advisor 2026-07-10)
    values, _ = _null_rail_pileup(values, lo, hi)

    if transform == "log10":
        with np.errstate(invalid="ignore", divide="ignore"):
            values = np.where(np.isfinite(values) & (values > 0), np.log10(values), np.nan)
    elif transform != "none":
        raise ValueError(f"Unknown transform {transform!r} for {label}")

    return _resample_nearest(depth_m, values, grid, tol), note


def harmonize_well(raw: RawWell, config: HarmonizationConfig) -> HarmonizedWell:
    """Harmonize one :class:`RawWell` to the canonical grid representation."""
    step = config.grid_step_m

    # Depth to metres.
    depth_raw = np.asarray(raw.depth, dtype=float)
    du = _normalize_unit(raw.depth_unit)
    depth_convert = {_normalize_unit(k): v for k, v in config.depth_convert.items()}
    if du in depth_convert:
        depth_m = depth_raw * depth_convert[du]
    elif du in ("", "m", "meter", "metre", "meters", "metres"):
        depth_m = depth_raw
    else:
        depth_m = depth_raw  # assume metres, flag below

    grid = _build_grid(depth_m, step)
    tol = step * 0.5 + 1e-6

    curves: dict[str, np.ndarray] = {}
    masks: dict[str, np.ndarray] = {}
    for canonical in config.canonical_curves:
        curves[canonical] = np.full(grid.shape, np.nan, dtype=float)
        masks[canonical] = np.zeros(grid.shape, dtype=bool)
    aux_curves: dict[str, np.ndarray] = {}
    aux_masks: dict[str, np.ndarray] = {}
    for aux in config.auxiliary_curves():
        aux_curves[aux] = np.full(grid.shape, np.nan, dtype=float)
        aux_masks[aux] = np.zeros(grid.shape, dtype=bool)

    unmapped: list[tuple[str, str]] = []
    unit_notes: list[str] = []
    if du not in depth_convert and du not in ("", "m", "meter", "metre", "meters", "metres"):
        unit_notes.append(f"DEPTH: unrecognized unit {raw.depth_unit!r}, assumed metres")

    claimed: dict[str, str] = {}

    for mnem, rc in raw.curves.items():
        if config.is_depth_alias(mnem):
            continue
        canonical = config.resolve_alias(mnem)
        if canonical is not None:
            if canonical in claimed:
                unit_notes.append(
                    f"{canonical}: multiple source mnemonics "
                    f"({claimed[canonical]!r} kept, {mnem!r} ignored)"
                )
                continue
            claimed[canonical] = mnem
            spec = config.curve(canonical)
            resampled, note = _process_channel(
                rc.data, rc.unit, spec.convert, spec.unit, spec.valid_range,
                spec.transform, depth_m, grid, tol, config.null_values, canonical,
            )
            curves[canonical] = resampled
            masks[canonical] = np.isfinite(resampled)
            if note:
                unit_notes.append(note)
            continue

        aux_name = config.resolve_aux_alias(mnem)
        if aux_name is not None:
            if aux_name in claimed:
                unit_notes.append(
                    f"{aux_name} (aux): multiple source mnemonics "
                    f"({claimed[aux_name]!r} kept, {mnem!r} ignored)"
                )
                continue
            claimed[aux_name] = mnem
            aspec = config.aux_curve(aux_name)
            resampled, note = _process_channel(
                rc.data, rc.unit, aspec.convert, aspec.unit, aspec.valid_range,
                aspec.transform, depth_m, grid, tol, config.null_values, f"{aux_name} (aux)",
            )
            aux_curves[aux_name] = resampled
            aux_masks[aux_name] = np.isfinite(resampled)
            if note:
                unit_notes.append(note)
            continue

        unmapped.append((mnem, rc.unit))

    present = [c for c in config.canonical_curves if bool(np.any(masks[c]))]

    # Usability: at least ``min_curves`` CANONICAL curves each covering at least
    # ``min_interval_m`` of valid thickness. Auxiliary curves never count here.
    n_curves_meeting = 0
    if grid.size:
        for c in present:
            coverage = float(np.count_nonzero(masks[c])) * step
            if coverage >= config.min_interval_m:
                n_curves_meeting += 1
    usable = n_curves_meeting >= config.min_curves

    return HarmonizedWell(
        well_id=raw.well_id,
        source=raw.source,
        depth_m=grid,
        grid_step_m=step,
        curves=curves,
        masks=masks,
        aux_curves=aux_curves,
        aux_masks=aux_masks,
        present_curves=present,
        usable=usable,
        unmapped=unmapped,
        unit_notes=unit_notes,
    )


def write_unmapped_csv(
    records: list[tuple[str, str, str, str]],
    path: Path | str,
) -> Path:
    """Aggregate and write unmapped mnemonics to reports/unmapped_mnemonics.csv.

    Each record is (source, well_id, raw_mnemonic, raw_unit). Rows are grouped
    by (source, raw_mnemonic, raw_unit) with an occurrence count, matching the
    triage contract in handoff Section 4.3. Existing entries are re-read and
    merged so the file accumulates across ingestion runs.
    """
    path = Path(path)
    counts: Counter[tuple[str, str, str]] = Counter()

    if path.exists():
        with path.open("r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                key = (row["source"], row["raw_mnemonic"], row["raw_unit"])
                counts[key] += int(row["count"])

    for source, _well_id, mnem, unit in records:
        counts[(source, mnem, unit)] += 1

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["source", "raw_mnemonic", "raw_unit", "count"])
        for (source, mnem, unit), count in sorted(counts.items(), key=lambda kv: -kv[1]):
            writer.writerow([source, mnem, unit, count])
    return path


def compute_norm_stats(
    wells: list[HarmonizedWell],
    config: HarmonizationConfig,
) -> dict[str, dict[str, float]]:
    """Per-curve robust normalization stats (median, IQR) over a well list.

    Contract: call this on the TRAINING split only (handoff Section 4.3). The
    result is versioned to JSON alongside the config version and consumed at
    train and inference time.
    """
    stats: dict[str, dict[str, float]] = {}
    for canonical in config.canonical_curves:
        pooled: list[np.ndarray] = []
        for w in wells:
            m = w.masks[canonical]
            if np.any(m):
                pooled.append(w.curves[canonical][m])
        if not pooled:
            continue
        arr = np.concatenate(pooled)
        median = float(np.median(arr))
        q75, q25 = np.percentile(arr, [75, 25])
        iqr = float(q75 - q25)
        stats[canonical] = {
            "median": median,
            "iqr": iqr if iqr > 0 else 1.0,
            "n_samples": int(arr.size),
        }
    return stats
