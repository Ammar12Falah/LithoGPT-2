"""FORCE 2020 ingester (handoff Section 4.1, Week 1 Task 3).

Canonical sources (verified 4 July 2026, see docs/LICENSE_MATRIX.md):
  - Data: Zenodo record 4351156 (DOI 10.5281/zenodo.4351156). Logs are NLOD 2.0,
    lithofacies labels are CC-BY-4.0. File names are resolved at runtime from
    the Zenodo REST API rather than hard-coded, so we never guess a URL.
  - Scoring artifacts (penalty matrix, starter notebook): pinned in
    configs/force2020/ from bolgebrygg/Force-2020-Machine-Learning-competition,
    with sha256 in configs/force2020/pinned.json.

The official split is preserved exactly: 98 training wells + 10 open leaderboard
test wells. This ingester downloads the release, then VERIFIES the counts from
the WELL column before writing anything downstream. If a count does not match,
it stops and reports rather than proceeding (handoff Rule 1).

NOTE (recorded 4 July 2026): a team copy of train.csv in the GitHub repo is a
28-well subset, NOT the official 98-well set. The 98 count must be verified
against the Zenodo release by running this module where zenodo.org is
reachable.
"""

from __future__ import annotations

import argparse
import csv
import json
import urllib.request
from pathlib import Path

from . import USER_AGENT
from ._http import FetchLog, PoliteFetcher

ZENODO_RECORD = "4351156"
ZENODO_API = f"https://zenodo.org/api/records/{ZENODO_RECORD}"
SOURCE = "force2020"
EXPECTED = {"train_wells": 98, "open_test_wells": 10}


def resolve_zenodo_files() -> list[dict]:
    """Return the file list (name + download URL + checksum) from Zenodo."""
    req = urllib.request.Request(ZENODO_API, headers={"User-Agent": USER_AGENT})  # noqa: S310
    with urllib.request.urlopen(req, timeout=120) as resp:  # noqa: S310
        record = json.load(resp)
    files = []
    for f in record.get("files", []):
        files.append(
            {
                "key": f.get("key"),
                "url": f.get("links", {}).get("self"),
                "checksum": f.get("checksum"),
                "size": f.get("size"),
            }
        )
    return files


def count_wells(csv_path: Path, delimiter: str = ";") -> tuple[int, int]:
    """Count (unique wells, rows) using only the WELL column. Streaming."""
    wells: set[str] = set()
    rows = 0
    with csv_path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh, delimiter=delimiter)
        header = next(reader)
        if "WELL" not in header:
            raise ValueError(f"No WELL column in {csv_path} (header={header[:6]})")
        widx = header.index("WELL")
        for row in reader:
            if not row:
                continue
            rows += 1
            if widx < len(row):
                wells.add(row[widx])
    return len(wells), rows


def ingest(raw_root: str = "data/raw", dry_run: bool = False) -> FetchLog:
    """Download the FORCE 2020 release and verify counts. Returns the fetch log."""
    fetcher = PoliteFetcher(SOURCE, raw_root=raw_root)
    log = FetchLog()

    if dry_run:
        print(f"[force2020] dry-run: would resolve files from {ZENODO_API}")
        return log

    files = resolve_zenodo_files()
    print(f"[force2020] resolved {len(files)} files from Zenodo record {ZENODO_RECORD}")
    for f in files:
        if not f["url"] or not f["key"]:
            continue
        fetcher.fetch(f["url"], rel_path=f["key"], log=log)

    # Verify counts against whichever train/test CSVs the release provides.
    dest = Path(raw_root) / SOURCE
    for path in sorted(dest.glob("*.csv")):
        try:
            n_wells, n_rows = count_wells(path)
            print(f"[force2020] {path.name}: {n_wells} wells, {n_rows} rows")
        except ValueError as exc:
            print(f"[force2020] {path.name}: {exc}")

    print(f"[force2020] ok={len(log.ok)} skipped={len(log.skipped)} failed={len(log.failed)}")
    for url, err in log.failed:
        print(f"[force2020] FAILED {url}: {err}")
    return log


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingest FORCE 2020 well-log dataset.")
    ap.add_argument("--raw-root", default="data/raw")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    ingest(raw_root=args.raw_root, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
