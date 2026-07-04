"""NLOG (Netherlands) ingester (handoff Section 4.1, Week 1 Task 5).

Verified 4 July 2026 (see docs/LICENSE_MATRIX.md): NLOG is the Dutch subsurface
portal run by TNO on behalf of the Ministry of Economic Affairs. Well logs
(LIS/LAS) become public after a statutory five-year confidentiality period;
administrative data is public immediately. The portal is bulk-friendly and a
complete dataset can be downloaded for some datatypes via the Datacenter.

Design: this ingester is INDEX-DRIVEN. Step 1 (obtain a borehole index with
per-borehole LAS download URLs) is a documented prerequisite because the exact
Datacenter bulk-download endpoint is not pinned here. We do not guess a URL
(handoff Rule 2 / escalation trigger "source blocking"): the index URL/format
is a PENDING INPUT to confirm from the NLOG Datacenter before the bulk run.

Once an index is supplied (CSV with columns: well_id, las_url), the fetch loop
is fully implemented: throttled, resumable, checksummed via PoliteFetcher.

Expected wall-clock for a bulk NLOG run at one request / 2 s is HOURS. State the
estimate before launch and run it as a resumable background job.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from ._http import FetchLog, PoliteFetcher

SOURCE = "nlog"

# PENDING INPUT: confirm the NLOG Datacenter bulk index endpoint and per-borehole
# LAS URL pattern before the bulk run. Do not guess. See docs/LICENSE_MATRIX.md.
INDEX_URL_UNVERIFIED = None
TERMS_URL = "https://www.nlog.nl/en/data"


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
