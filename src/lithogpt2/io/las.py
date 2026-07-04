"""LAS parsing into a source-agnostic RawWell container.

Wraps ``lasio`` so the rest of the pipeline never depends on lasio's object
model directly. Reading is deliberately tolerant: some public LAS files have
non-standard encodings or malformed headers, and the ingestion contract is to
record failures verbatim rather than crash a bulk run.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import lasio
import numpy as np


@dataclass
class RawCurve:
    mnemonic: str
    unit: str
    data: np.ndarray


@dataclass
class RawWell:
    """Raw, un-harmonized well as read from a LAS file.

    depth is the index curve in its declared unit (``depth_unit``); curves are
    keyed by their raw mnemonic exactly as written in the file so that
    harmonization, not I/O, owns the alias mapping.
    """

    well_id: str
    source: str
    depth: np.ndarray
    depth_unit: str
    curves: dict[str, RawCurve]
    path: Path | None = None
    header: dict[str, str] = None  # selected ~W section items

    def curve_mnemonics(self) -> list[str]:
        return list(self.curves.keys())


def read_las(
    path: Path | str,
    source: str,
    well_id: str | None = None,
) -> RawWell:
    """Read a LAS file into a :class:`RawWell`.

    Raises the underlying exception on unreadable files; callers in the
    ingestion layer catch and log these so a single bad file never aborts a
    bulk job.
    """
    path = Path(path)
    las = lasio.read(str(path), engine="normal")

    # Index curve is the first curve in a well-formed LAS; lasio exposes it.
    depth = np.asarray(las.index, dtype=float)
    depth_unit = ""
    if las.curves and len(las.curves) > 0:
        depth_unit = (las.curves[0].unit or "").strip()

    curves: dict[str, RawCurve] = {}
    for item in las.curves[1:]:  # skip the index curve
        mnem = item.mnemonic.strip()
        curves[mnem] = RawCurve(
            mnemonic=mnem,
            unit=(item.unit or "").strip(),
            data=np.asarray(item.data, dtype=float),
        )

    # Resolve a stable well id: prefer explicit arg, then UWI/API, then WELL.
    wid = well_id
    if wid is None:
        for key in ("UWI", "API", "WELL"):
            try:
                val = las.well[key].value
            except Exception:  # noqa: BLE001 - lasio raises varied errors
                val = None
            if val:
                wid = str(val).strip()
                break
    if not wid:
        wid = path.stem

    header: dict[str, str] = {}
    for key in ("WELL", "UWI", "API", "FLD", "LOC", "STRT", "STOP", "STEP", "NULL"):
        try:
            header[key] = str(las.well[key].value)
        except Exception:  # noqa: BLE001, S112
            continue

    return RawWell(
        well_id=str(wid),
        source=source,
        depth=depth,
        depth_unit=depth_unit,
        curves=curves,
        path=path,
        header=header,
    )
