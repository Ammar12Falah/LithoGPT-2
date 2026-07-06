"""Iterate a directory of mixed LAS and DLIS files into RawWell objects.

Used by the NLOG pass, where one borehole can carry several log files (multiple
LAS, one or more DLIS) downloaded as ``{borehole_code}__{file_id}.{ext}``. This
groups files by borehole and yields exactly one RawWell per borehole: the
richest single file (most raw curves, tie-broken by depth span). That keeps the
QC denominator equal to the borehole count, not the file count, so the G2
European-well bar is measured in wells. Union-of-curves across a borehole's
files is deferred (see io/dlis.py for the same per-frame simplification).

Robustness matches ingest/las_dir.py: each read is given a hard time budget via
SIGALRM (a malformed LAS or DLIS can stall a parser rather than raise), and the
borehole currently being read is written to logs/nlog_current.txt so a long
read is visible from outside. Both guards are no-ops off the main thread.
"""
from __future__ import annotations

import signal
from collections import defaultdict
from collections.abc import Iterator
from pathlib import Path

import numpy as np

from ..io.dlis import read_dlis
from ..io.las import RawWell, read_las

_READ_TIMEOUT_S = 90  # DLIS can be slower than LAS; still only trips on stalls
_MARKER = Path("logs") / "nlog_current.txt"


class _ReadTimeout(Exception):
    pass


def _raise_read_timeout(signum, frame):  # noqa: ARG001
    raise _ReadTimeout()


def _arm_timeout() -> bool:
    if not hasattr(signal, "SIGALRM"):
        return False
    try:
        signal.signal(signal.SIGALRM, _raise_read_timeout)
        return True
    except (ValueError, OSError):  # not the main thread
        return False


def _mark(text: str) -> None:
    try:
        _MARKER.parent.mkdir(parents=True, exist_ok=True)
        _MARKER.write_text(text)
    except OSError:
        pass


def _borehole_id(path: Path) -> str:
    """Borehole code from ``{borehole_code}__{file_id}.{ext}`` (stem before __)."""
    stem = path.stem
    return stem.split("__", 1)[0] if "__" in stem else stem


def _read_any(path: Path, source: str, well_id: str) -> RawWell:
    if path.suffix.lower() == ".dlis":
        return read_dlis(path, source=source, well_id=well_id)
    return read_las(path, source=source, well_id=well_id)


def _depth_span(raw: RawWell) -> float:
    finite = raw.depth[np.isfinite(raw.depth)]
    return float(finite.max() - finite.min()) if finite.size else 0.0


def iter_nlog_wells(
    well_dir: str | Path,
    source: str,
    failures: list[tuple[str, str]] | None = None,
    max_wells: int | None = None,
    skip_ids: set[str] | None = None,
    selected: dict[str, str] | None = None,
) -> Iterator[tuple[str, RawWell]]:
    """Yield (borehole_id, RawWell) for each borehole under ``well_dir``.

    Files are grouped by borehole; the richest readable file per borehole
    (most curves, then widest depth span) is yielded with its well_id set to
    the borehole code. Files that fail to read (raising or exceeding the read
    budget) are recorded in ``failures`` as (name, error) and skipped; a
    borehole with no readable file is recorded once and skipped.

    If ``selected`` is given, the winning file's name is recorded per borehole
    (advisor decision 2), so a metadata pre-selection rule can be validated
    against the file the curve-count iterator actually chose.
    """
    d = Path(well_dir)
    exts = {".las", ".dlis"}
    paths = sorted(p for p in d.iterdir() if p.suffix.lower() in exts) if d.exists() else []
    groups: dict[str, list[Path]] = defaultdict(list)
    for p in paths:
        groups[_borehole_id(p)].append(p)

    skip = skip_ids or set()
    use_alarm = _arm_timeout()
    n = 0
    for bid in sorted(groups):
        if bid in skip:
            continue
        best: tuple[tuple[int, float], RawWell] | None = None
        for p in groups[bid]:
            _mark(f"{bid} :: {p.name}")
            if use_alarm:
                signal.alarm(_READ_TIMEOUT_S)
            try:
                raw = _read_any(p, source, bid)
            except _ReadTimeout:
                if failures is not None:
                    failures.append((p.name, f"read timeout > {_READ_TIMEOUT_S}s (skipped)"))
                continue
            except Exception as e:  # noqa: BLE001 - bulk robustness; record and continue
                if failures is not None:
                    failures.append((p.name, f"{type(e).__name__}: {e}"))
                continue
            finally:
                if use_alarm:
                    signal.alarm(0)
            score = (len(raw.curves), _depth_span(raw))
            if best is None or score > best[0]:
                best = (score, raw)
        if best is None:
            if failures is not None:
                failures.append((bid, "no readable log file for borehole"))
            continue
        if selected is not None and best[1].path is not None:
            # Records which file won (most curves, widest span) so a metadata rule
            # for at-scale pre-selection can be validated against real choices.
            selected[bid] = best[1].path.name
        yield bid, best[1]
        n += 1
        if max_wells is not None and n >= max_wells:
            return
