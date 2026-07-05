"""Iterate a directory of LAS files into RawWell objects (for KGS, and any
LAS-file source). Reading is tolerant: a single malformed LAS is recorded as a
failure and skipped, never aborting a bulk run.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from ..io.las import RawWell, read_las


def iter_las_wells(
    las_dir: str | Path,
    source: str,
    failures: list[tuple[str, str]] | None = None,
    max_wells: int | None = None,
    skip_stems: set[str] | None = None,
) -> Iterator[tuple[str, RawWell]]:
    """Yield (well_id, RawWell) for each readable LAS file under ``las_dir``.

    well_id is the file stem. Unreadable files are appended to ``failures`` as
    (stem, error) and skipped. ``max_wells`` caps the number of successful
    wells yielded (useful for smoke runs on a big corpus). ``skip_stems`` is a
    set of file stems to skip before reading, so an incremental or sharded run
    does not re-read wells already processed in a previous run.
    """
    d = Path(las_dir)
    paths = sorted(p for p in d.iterdir() if p.suffix.lower() == ".las") if d.exists() else []
    skip = skip_stems or set()
    n = 0
    for p in paths:
        if p.stem in skip:
            continue
        try:
            raw = read_las(p, source=source, well_id=p.stem)
        except Exception as e:  # noqa: BLE001 - bulk robustness; record and continue
            if failures is not None:
                failures.append((p.stem, f"{type(e).__name__}: {e}"))
            continue
        yield p.stem, raw
        n += 1
        if max_wells is not None and n >= max_wells:
            return
