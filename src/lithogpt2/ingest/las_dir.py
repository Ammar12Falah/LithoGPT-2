"""Iterate a directory of LAS files into RawWell objects (for KGS, and any
LAS-file source). Reading is tolerant: a single malformed LAS is recorded as a
failure and skipped, never aborting a bulk run.

Robustness against hangs: a malformed LAS can make the reader loop or stall
rather than raise. Each read is therefore given a hard time budget
(_READ_TIMEOUT_S); a file that exceeds it is recorded as a failure and skipped,
so one bad file cannot freeze a bulk run. The stem currently being read is
written to a marker file (logs/kgs_current.txt) so a long read is visible from
outside. Both guards are best-effort and no-ops off the main thread (e.g. in
tests), where SIGALRM cannot be armed.
"""

from __future__ import annotations

import signal
from collections.abc import Iterator
from pathlib import Path

from ..io.las import RawWell, read_las

# A healthy LAS reads in well under a second. This ceiling only trips on files
# that stall the parser. Generous so a large-but-valid log is never false-skipped.
_READ_TIMEOUT_S = 60
_MARKER = Path("logs") / "kgs_current.txt"


class _ReadTimeout(Exception):
    pass


def _raise_read_timeout(signum, frame):  # noqa: ARG001
    raise _ReadTimeout()


def _arm_timeout() -> bool:
    """Register the SIGALRM handler if on the main thread. Returns usability."""
    if not hasattr(signal, "SIGALRM"):
        return False
    try:
        signal.signal(signal.SIGALRM, _raise_read_timeout)
        return True
    except (ValueError, OSError):  # not the main thread
        return False


def _mark(stem: str) -> None:
    try:
        _MARKER.parent.mkdir(parents=True, exist_ok=True)
        _MARKER.write_text(stem)
    except OSError:
        pass


def iter_las_wells(
    las_dir: str | Path,
    source: str,
    failures: list[tuple[str, str]] | None = None,
    max_wells: int | None = None,
    skip_stems: set[str] | None = None,
) -> Iterator[tuple[str, RawWell]]:
    """Yield (well_id, RawWell) for each readable LAS file under ``las_dir``.

    well_id is the file stem. Unreadable files (raising, or exceeding the read
    time budget) are appended to ``failures`` as (stem, error) and skipped.
    ``max_wells`` caps successful wells yielded. ``skip_stems`` skips stems
    already processed in a previous run before the expensive read.
    """
    d = Path(las_dir)
    paths = sorted(p for p in d.iterdir() if p.suffix.lower() == ".las") if d.exists() else []
    skip = skip_stems or set()
    use_alarm = _arm_timeout()
    n = 0
    for p in paths:
        if p.stem in skip:
            continue
        _mark(p.stem)
        if use_alarm:
            signal.alarm(_READ_TIMEOUT_S)
        try:
            raw = read_las(p, source=source, well_id=p.stem)
        except _ReadTimeout:
            if failures is not None:
                failures.append((p.stem, f"read timeout > {_READ_TIMEOUT_S}s (skipped)"))
            continue
        except Exception as e:  # noqa: BLE001 - bulk robustness; record and continue
            if failures is not None:
                failures.append((p.stem, f"{type(e).__name__}: {e}"))
            continue
        finally:
            if use_alarm:
                signal.alarm(0)
        yield p.stem, raw
        n += 1
        if max_wells is not None and n >= max_wells:
            return
