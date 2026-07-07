"""Iterate a directory of mixed LAS and DLIS files into RawWell objects.

Used by the NLOG pass, where one borehole can carry several log files (multiple
LAS, one or more DLIS) downloaded as ``{borehole_code}__{file_id}.{ext}``. This
groups files by borehole and yields exactly one RawWell per borehole: the
richest single file (most raw curves, tie-broken by depth span). That keeps the
QC denominator equal to the borehole count, not the file count, so the G2
European-well bar is measured in wells. Union-of-curves across a borehole's
files is deferred (see io/dlis.py for the same per-frame simplification).

Read timeout that actually holds: each file is read in a forked child process
with a hard wall-clock cap. If a parser hangs (a pathological DLIS can spin
inside dlisio's C code, where a SIGALRM handler never runs because control
never returns to Python), the child is terminated and killed and the file is
logged and skipped. This is the fix for the batch-1 stall: the earlier SIGALRM
guard was a no-op both off the main thread and against a C-level hang. The
borehole currently being read is written to logs/nlog_current.txt so a long
read is visible from outside.
"""
from __future__ import annotations

import multiprocessing as mp
import queue as _queue
from collections import defaultdict
from collections.abc import Iterator
from pathlib import Path

import numpy as np

from ..io.dlis import read_dlis
from ..io.las import RawWell, read_las

_READ_TIMEOUT_S = 120  # a real read is seconds; a hang is minutes. Skip past this.
_MARKER = Path("logs") / "nlog_current.txt"


class _ReadTimeout(Exception):
    pass


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


def _read_dispatch(path: Path, source: str, well_id: str) -> RawWell:
    if path.suffix.lower() == ".dlis":
        return read_dlis(path, source=source, well_id=well_id)
    return read_las(path, source=source, well_id=well_id)


def _read_worker(path_str: str, source: str, well_id: str, q) -> None:
    """Child-process entry: read one file, put ("ok", RawWell) or ("err", msg)."""
    try:
        raw = _read_dispatch(Path(path_str), source, well_id)
        q.put(("ok", raw))
    except BaseException as e:  # noqa: BLE001 - report anything, including odd C errors
        q.put(("err", f"{type(e).__name__}: {e}"))


def _read_with_timeout(path: Path, source: str, well_id: str,
                       timeout_s: float = _READ_TIMEOUT_S,
                       start_method: str | None = None) -> RawWell:
    """Read one file in a child process, killing it if it exceeds ``timeout_s``.

    Uses the ``fork`` start method: the child is a copy of the parent, so it
    works in every invocation context (subprocess, notebook, stdin) without the
    re-import that makes ``forkserver`` and ``spawn`` fail on a non-file main
    module. ``run_qc_nlog`` is single-threaded when it reads, so the classic
    multi-threaded-fork deadlock does not apply here. Falls back to an
    in-process read if ``fork`` is unavailable (non-Linux). Raises _ReadTimeout
    on a hang or a child crash that produced no result, or RuntimeError with the
    child's message if the read itself failed. The hard kill is what makes a
    C-level parser hang unable to outlast the budget.
    """
    ctx = None
    for name in ([start_method] if start_method else ["fork"]):
        try:
            ctx = mp.get_context(name)
            break
        except (ValueError, RuntimeError):
            continue
    if ctx is None:
        # No suitable child-process context: in-process read, no hard cap.
        return _read_dispatch(path, source, well_id)

    q: mp.Queue = ctx.Queue()
    proc = ctx.Process(target=_read_worker, args=(str(path), source, well_id, q),
                       daemon=True)
    proc.start()
    try:
        status, payload = q.get(timeout=timeout_s)  # drain before join (large object)
    except _queue.Empty:
        proc.terminate()
        proc.join(5)
        if proc.is_alive():
            proc.kill()
            proc.join(5)
        raise _ReadTimeout()
    proc.join(5)
    if proc.is_alive():
        proc.terminate()
    if status == "ok":
        return payload
    raise RuntimeError(payload)


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
    read_timeout_s: float = _READ_TIMEOUT_S,
) -> Iterator[tuple[str, RawWell]]:
    """Yield (borehole_id, RawWell) for each borehole under ``well_dir``.

    Files are grouped by borehole; the richest readable file per borehole
    (most curves, then widest depth span) is yielded with its well_id set to
    the borehole code. A file that fails to read (raising, or exceeding the
    per-file timeout, or crashing its reader child) is recorded in ``failures``
    as (name, error) and skipped; a borehole with no readable file is recorded
    once and skipped.

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
    n = 0
    for bid in sorted(groups):
        if bid in skip:
            continue
        best: tuple[tuple[int, float], RawWell] | None = None
        for p in groups[bid]:
            _mark(f"{bid} :: {p.name}")
            try:
                raw = _read_with_timeout(p, source, bid, read_timeout_s)
            except _ReadTimeout:
                if failures is not None:
                    failures.append((p.name, f"read timeout > {read_timeout_s:.0f}s (killed, skipped)"))
                continue
            except Exception as e:  # noqa: BLE001 - bulk robustness; record and continue
                if failures is not None:
                    failures.append((p.name, f"{type(e).__name__}: {e}"))
                continue
            score = (len(raw.curves), _depth_span(raw))
            if best is None or score > best[0]:
                best = (score, raw)
        if best is None:
            if failures is not None:
                failures.append((bid, "no readable log file for borehole"))
            continue
        if selected is not None and best[1].path is not None:
            selected[bid] = best[1].path.name
        yield bid, best[1]
        n += 1
        if max_wells is not None and n >= max_wells:
            return
