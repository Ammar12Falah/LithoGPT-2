"""DLIS parsing into the same RawWell container used for LAS.

NLOG serves a large share of its logs as DLIS rather than LAS. dlisio reads
them; this module reduces a DLIS file to one RawWell so the harmonization and
QC pipeline treats DLIS and LAS identically and never learns dlisio's object
model.

A DLIS file can hold several logical files, each with several frames (logging
runs or passes), and only some frames are depth-indexed. v1 policy, documented
for advisor review: pick the single richest depth-indexed frame in the file
(most scalar channels, tie-broken by depth span) and return it as one RawWell.
Merging curves across frames onto a common depth grid is deferred; within a
frame the main log usually carries the standard curve suite, which is what the
minimum-interval QC check needs.

Depth is converted to metres here and reported as unit "m", because DLIS index
channels are commonly stored in tenths of an inch ("0.1 in") or feet, while the
harmonizer's depth-unit table only knows feet. Converting at read time keeps
depth correct regardless of the source unit and never depends on the YAML
knowing an exotic DLIS unit.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from .las import RawCurve, RawWell

# Depth unit -> metres. Keys are normalized (lowercased; spaces, dots and
# underscores stripped) so "0.1 in", "0.1in" and "0.1_IN" all match "01in".
_DEPTH_TO_M: dict[str, float] = {
    "m": 1.0, "meter": 1.0, "metre": 1.0, "meters": 1.0, "metres": 1.0,
    "ft": 0.3048, "f": 0.3048, "feet": 0.3048, "foot": 0.3048,
    "in": 0.0254, "inch": 0.0254, "inches": 0.0254,
    "01in": 0.00254,  # tenths of an inch: TDEP is frequently stored this way
    "mm": 0.001, "cm": 0.01,
}

_DEPTH_INDEX_NAMES = {"DEPT", "DEPTH", "MD", "TDEP", "DMD", "TVD"}


def _norm_unit(u: str | None) -> str:
    return (u or "").strip().lower().replace(" ", "").replace(".", "").replace("_", "")


def _depth_factor_m(unit: str | None) -> float | None:
    """Metres per source unit for a depth unit string, or None if unrecognized."""
    return _DEPTH_TO_M.get(_norm_unit(unit))


def _channel_name(ch) -> str:
    return str(getattr(ch, "name", "") or "").strip()


def _is_scalar(ch) -> bool:
    """True for a per-depth scalar channel. Array channels (dimension != [1])
    are skipped: they are image or waveform tools, never canonical log curves."""
    dim = getattr(ch, "dimension", None)
    if not dim:
        return True  # unknown -> treat as scalar; the length check gates it anyway
    try:
        return list(dim) == [1]
    except TypeError:
        return True


def _frame_to_rawwell(frame, source: str, well_id, path) -> RawWell | None:
    """Reduce one DLIS frame to a RawWell, or None if it is not depth-usable."""
    itype = str(getattr(frame, "index_type", "") or "").lower()
    if "time" in itype:
        return None  # time-indexed frame cannot map to a depth grid

    index_name = str(getattr(frame, "index", "") or "").strip()
    depth_ch = None
    for ch in frame.channels:
        if _channel_name(ch) == index_name:
            depth_ch = ch
            break
    if depth_ch is None:
        return None

    factor = _depth_factor_m(getattr(depth_ch, "units", ""))
    if factor is None:
        # Unknown index unit: accept only if the index name is unambiguously a
        # depth channel, then assume metres. Otherwise refuse rather than guess
        # a scale (a wrong factor would silently corrupt every depth).
        if index_name.upper() not in _DEPTH_INDEX_NAMES:
            return None
        factor = 1.0

    try:
        depth_raw = np.asarray(depth_ch.curves(), dtype=float).ravel()
    except Exception:  # noqa: BLE001 - dlisio raises varied errors on bad frames
        return None
    if depth_raw.size == 0 or not np.any(np.isfinite(depth_raw)):
        return None
    depth_m = depth_raw * factor
    n = depth_m.size

    curves: dict[str, RawCurve] = {}
    for ch in frame.channels:
        name = _channel_name(ch)
        if not name or name == index_name or not _is_scalar(ch):
            continue
        try:
            data = np.asarray(ch.curves(), dtype=float).ravel()
        except Exception:  # noqa: BLE001
            continue
        if data.size != n:
            continue  # cannot align to this frame's depth
        curves[name] = RawCurve(
            mnemonic=name,
            unit=str(getattr(ch, "units", "") or "").strip(),
            data=data,
        )

    if not curves:
        return None

    wid = str(well_id) if well_id else (path.stem if path else "dlis")
    return RawWell(
        well_id=wid,
        source=source,
        depth=depth_m,
        depth_unit="m",
        curves=curves,
        path=path,
        header={"index_channel": index_name},
    )


def read_dlis(path: Path | str, source: str, well_id: str | None = None) -> RawWell:
    """Read a DLIS file into a single RawWell: the richest depth-indexed frame.

    Raises on a file with no usable depth-indexed frame; the ingestion layer
    catches and logs these so one bad DLIS never aborts a bulk run.
    """
    from dlisio import dlis  # lazy import so LAS-only paths need no dlisio

    path = Path(path)
    best: tuple[tuple[int, float], RawWell] | None = None
    with dlis.load(str(path)) as files:
        for lf in files:
            for frame in lf.frames:
                try:
                    raw = _frame_to_rawwell(frame, source, well_id, path)
                except Exception:  # noqa: BLE001 - bulk robustness
                    raw = None
                if raw is None:
                    continue
                finite = raw.depth[np.isfinite(raw.depth)]
                span = float(finite.max() - finite.min()) if finite.size else 0.0
                score = (len(raw.curves), span)
                if best is None or score > best[0]:
                    best = (score, raw)
    if best is None:
        raise ValueError("no depth-indexed frame with scalar curves in DLIS")
    return best[1]
