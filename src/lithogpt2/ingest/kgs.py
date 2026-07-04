"""KGS (Kansas) ingester (SCHEDULED: week 2, handoff Section 4.1).

Verified 4 July 2026 (see docs/LICENSE_MATRIX.md): the Kansas Geological Survey
(kgs.ku.edu) publishes free LAS files for released wells after a two-year
confidentiality period, plus a queryable Magellan index and a pre-created ZIP
containing the data for all wells with LAS files.

Plan (week 2): download the index first, then fetch LAS archives, throttled and
resumable via PoliteFetcher. Redistribution of raw KGS LAS is UNCLEAR (some
KGS-hosted data is third-party IHS-licensed and non-redistributable), so the
default posture is pipeline + weights, no raw mirror. Confirm the LAS terms
before any redistribution.

Interface frozen now; body guarded until week 2.
"""

from __future__ import annotations

from ._http import FetchLog, PoliteFetcher

SOURCE = "kgs"
INDEX_PAGE = "https://www.kgs.ku.edu/Magellan/Logs/"
_WEEK2 = "Scheduled for week 2 (handoff Section 4.1); not yet implemented."


def ingest(raw_root: str = "data/raw") -> FetchLog:
    _ = PoliteFetcher  # keep the dependency contract explicit
    raise NotImplementedError(_WEEK2)
