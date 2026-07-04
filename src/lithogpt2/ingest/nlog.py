"""NLOG (Netherlands) ingester (handoff Section 4.1, Week 1 Task 5).

Verified 4 July 2026 (see docs/LICENSE_MATRIX.md): NLOG is the Dutch subsurface
portal run by TNO on behalf of the Ministry of Economic Affairs. Well logs
(LIS/LAS) become public after a statutory five-year confidentiality period;
administrative data is public immediately. The portal is bulk-friendly and a
complete dataset can be downloaded for some datatypes via the Datacenter.

Verified index sources (see docs/NLOG_ACCESS.md for the full map):
  - Borehole overview UI: https://www.nlog.nl/datacenter/brh-overview
  - Interactive map: https://www.nlog.nl/nlog-mapviewer/
  - Backing ArcGIS server (queryable borehole index, no scraping):
    https://www.gdngeoservices.nl/arcgis/rest/services/nlog
  - Log files (LIS/LAS/DLIS) are per-borehole, released after a five-year
    confidentiality period, named NLOG_LIS_LAS_{fileid}_... and served by
    numeric asset id (cf. https://www.nlog.nl/media/{id}).

Design: this ingester is INDEX-DRIVEN. Two concrete URLs remain to be CONFIRMED
(not guessed, per handoff Rule 2): (a) the exact ArcGIS borehole layer query URL
under the nlog folder above, and (b) the per-file LAS download URL returned by
the Datacenter file-list call. docs/NLOG_ACCESS.md gives a two-minute browser
capture to confirm both. Once an index is supplied (CSV with columns:
well_id, las_url), the fetch loop below is fully implemented: throttled,
resumable, checksummed via PoliteFetcher.

Expected wall-clock for a bulk NLOG run at one request / 2 s is HOURS. State the
estimate before launch and run it as a resumable background job.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from ._http import FetchLog, PoliteFetcher

SOURCE = "nlog"

# Verified index sources (documented facts, not guessed download endpoints).
DATACENTER_OVERVIEW = "https://www.nlog.nl/datacenter/brh-overview"
MAPVIEWER = "https://www.nlog.nl/nlog-mapviewer/"
ARCGIS_NLOG_FOLDER = "https://www.gdngeoservices.nl/arcgis/rest/services/nlog"
TERMS_URL = "https://www.nlog.nl/en/data"
DISCLAIMER_URL = "https://www.nlog.nl/en/disclaimer"
# TO CONFIRM (see docs/NLOG_ACCESS.md): exact ArcGIS borehole layer query URL and
# the per-file LAS download URL. Do not guess these.
ARCGIS_BOREHOLE_LAYER_TO_CONFIRM = None
LAS_DOWNLOAD_URL_PATTERN_TO_CONFIRM = None


def ingest_from_index(index_csv: str, raw_root: str = "data/raw") -> FetchLog:
    """Fetch every LAS in a supplied index CSV (columns: well_id, las_url)."""
    fetcher = PoliteFetcher(SOURCE, raw_root=raw_root)
    log = FetchLog()
    index_path = Path(index_csv)
    if not index_path.exists():
        raise FileNotFoundError(
            f"NLOG index not found: {index_csv}. Obtain a borehole index with "
            f"per-well LAS URLs from the NLOG Datacenter first (terms: {TERMS_URL})."
        )
    with index_path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        n = 0
        for row in reader:
            well_id = row["well_id"].strip()
            url = row["las_url"].strip()
            if not url:
                continue
            n += 1
            fetcher.fetch(url, rel_path=f"wells/{well_id}.las", log=log)
    print(
        f"[nlog] indexed={n} ok={len(log.ok)} skipped={len(log.skipped)} "
        f"failed={len(log.failed)}"
    )
    for url, err in log.failed:
        print(f"[nlog] FAILED {url}: {err}")
    return log


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingest NLOG well logs from an index.")
    ap.add_argument(
        "--index-csv",
        required=True,
        help="Path to a CSV with columns well_id,las_url (from the NLOG Datacenter).",
    )
    ap.add_argument("--raw-root", default="data/raw")
    args = ap.parse_args()
    ingest_from_index(args.index_csv, raw_root=args.raw_root)


if __name__ == "__main__":
    main()
