"""Verification guard: fail loudly on an empty target set. See OPERATING_RULES.md."""
from __future__ import annotations

import os


def require_nonempty(paths, label: str, min_count: int = 1):
    """Assert a scanned target set is non-empty; print the resolved dir it scanned.

    paths: list of file paths the verifier is about to scan.
    Raises AssertionError (loud, non-zero exit in a script) if fewer than min_count.
    """
    n = len(paths)
    resolved = os.path.dirname(os.path.abspath(paths[0])) if paths else os.getcwd()
    print(f"[verify:{label}] scanning {n} items under {resolved}", flush=True)
    assert n >= min_count, (
        f"[verify:{label}] EMPTY/short target set: found {n} (< {min_count}). "
        f"Resolved dir: {resolved}. Refusing to report a pass on nothing scanned."
    )
    return n
