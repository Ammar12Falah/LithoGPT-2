"""KGS (Kansas Geological Survey) ingester (handoff Section 4.1).

Verified 4 July 2026 (endpoints checked live; see docs/KGS_ACCESS.md and
docs/LICENSE_MATRIX.md). KGS is the volume anchor for Gate G1: 21,780 digital
LAS wireline logs as of 31 Dec 2024. LAS files for released wells are free to
download after a two-year confidentiality period, for public service and
research (https://www.kgs.ku.edu/Publications/Bulletins/LA/02_digital.html).

Access model (cleaner than per-well fetch): the entire LAS corpus is published
as per-year archive ZIPs under PRS/Scans/Log_Summary/, plus ks_las_files.zip as
the metadata index that connects LAS files to wells. So the whole corpus is a
handful of bulk requests, not 21,780 polite ones.

  index    : https://www.kgs.ku.edu/PRS/Ora_Archive/ks_las_files.zip
  archives : https://www.kgs.ku.edu/PRS/Scans/Log_Summary/<name>.zip

Redistribution of raw KGS LAS is UNCLEAR (some KGS-hosted data, e.g. pre-1987
production and certain scanned material, is IHS-licensed and may not be
redistributed). The LAS wireline logs themselves are the free public set, but
under the default posture we release pipeline + weights + attribution, no raw
mirror. Attribution: "Kansas Geological Survey (KGS), University of Kansas."
"""

from __future__ import annotations

import argparse
import csv
import zipfile
from pathlib import Path

from ._http import FetchLog, PoliteFetcher

SOURCE = "kgs"

INDEX_PAGE = "https://www.kgs.ku.edu/Magellan/Logs/"
INDEX_ZIP = "https://www.kgs.ku.edu/PRS/Ora_Archive/ks_las_files.zip"
ARCHIVE_BASE = "https://www.kgs.ku.edu/PRS/Scans/Log_Summary/"
LICENSE_CITE = "https://www.kgs.ku.edu/Publications/Bulletins/LA/02_digital.html"

# Per-year LAS archives (name -> (approx size, file count) for planning), from
# the verified Log_Summary listing (4 July 2026). Two hrefs were confirmed
# explicitly (2001_2005, 2006_2011); the rest share the same base path.
ARCHIVE_ZIPS: dict[str, tuple[str, int]] = {
    "1999.zip": ("166 MB", 2061),
    "2001_2005.zip": ("44 MB", 1498),
    "2006_2011.zip": ("425 MB", 2360),
    "2012.zip": ("678 MB", 2263),
    "2013.zip": ("819 MB", 2330),
    "2014.zip": ("1.2 GB", 3231),
    "2015.zip": ("864 MB", 2082),
    "2016.zip": ("1.0 GB", 2283),
    "2017.zip": ("465 MB", 894),
    "2018.zip": ("175 MB", 356),
    "2019.zip": ("279 MB", 546),
    "2020.zip": ("308 MB", 539),
    "2021.zip": ("339 MB", 592),
    "2022.zip": ("152 MB", 266),
    "2023.zip": ("352 MB", 708),
    "2024.zip": ("856 MB", 3810),
    "2025.zip": ("235 MB", 767),
}

# A subset that already clears the G1 5,000-well target in a few downloads.
RECOMMENDED_G1_YEARS = ["2024.zip", "2014.zip", "2016.zip"]  # ~9,324 LAS files


def fetch_index(raw_root: str = "data/raw") -> Path:
    """Download and unzip ks_las_files.zip. Returns the extracted index file."""
    fetcher = PoliteFetcher(SOURCE, raw_root=raw_root)
    log = FetchLog()
    fetcher.fetch(INDEX_ZIP, rel_path="ks_las_files.zip", log=log)
    dest = Path(raw_root) / SOURCE
    zpath = dest / "ks_las_files.zip"
    if not zpath.exists():
        raise FileNotFoundError(f"index not downloaded: {zpath} (log: {log.failed})")
    with zipfile.ZipFile(zpath) as zf:
        zf.extractall(dest / "index")
    extracted = sorted((dest / "index").glob("*"))
    if not extracted:
        raise FileNotFoundError("ks_las_files.zip contained no files")
    # Prefer a text/csv-like member.
    for e in extracted:
        if e.suffix.lower() in (".txt", ".csv", ".dat", ""):
            return e
    return extracted[0]


def parse_index(index_path: str | Path) -> tuple[list[str], list[dict[str, str]]]:
    """Parse the KGS well index, sniffing the delimiter. Returns (header, rows).

    Column names are taken from the file's own header. API/KID/LAS columns are
    exposed as-is; the caller decides how to join to LAS files. No columns are
    invented.
    """
    p = Path(index_path)
    with p.open("r", encoding="utf-8", errors="replace", newline="") as fh:
        sample = fh.read(8192)
        fh.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",\t|;")
        except csv.Error:
            dialect = csv.excel  # default to comma
        reader = csv.DictReader(fh, dialect=dialect)
        header = list(reader.fieldnames or [])
        rows = [dict(r) for r in reader]
    return header, rows


def fetch_archives(
    years: list[str] | None = None, raw_root: str = "data/raw"
) -> FetchLog:
    """Download selected per-year LAS archive ZIPs (resumable, checksummed).

    Large: these total several GB across all years. Default is the G1 subset.
    State the expected wall-clock before launching a full pull.
    """
    years = years or RECOMMENDED_G1_YEARS
    unknown = [y for y in years if y not in ARCHIVE_ZIPS]
    if unknown:
        raise ValueError(f"Unknown archive(s): {unknown}. Valid: {sorted(ARCHIVE_ZIPS)}")
    fetcher = PoliteFetcher(SOURCE, raw_root=raw_root)
    log = FetchLog()
    for name in years:
        fetcher.fetch(ARCHIVE_BASE + name, rel_path=f"archives/{name}", log=log)
    print(f"[kgs] archives ok={len(log.ok)} skipped={len(log.skipped)} failed={len(log.failed)}")
    for url, err in log.failed:
        print(f"[kgs] FAILED {url}: {err}")
    return log


def unpack_las(raw_root: str = "data/raw") -> int:
    """Extract .las files from downloaded archive ZIPs into kgs/las/. Returns count."""
    dest = Path(raw_root) / SOURCE
    arch_dir = dest / "archives"
    out = dest / "las"
    out.mkdir(parents=True, exist_ok=True)
    n = 0
    for zpath in sorted(arch_dir.glob("*.zip")):
        with zipfile.ZipFile(zpath) as zf:
            for member in zf.namelist():
                if member.lower().endswith(".las"):
                    target = out / Path(member).name
                    if target.exists():
                        continue
                    with zf.open(member) as src, target.open("wb") as dst:
                        dst.write(src.read())
                    n += 1
    print(f"[kgs] unpacked {n} LAS files to {out}")
    return n


def ingest(
    raw_root: str = "data/raw",
    years: list[str] | None = None,
    index_only: bool = False,
    dry_run: bool = False,
) -> FetchLog:
    """Fetch the index, then (unless index_only) the archives, then unpack LAS."""
    years = years or RECOMMENDED_G1_YEARS
    if dry_run:
        planned = sum(ARCHIVE_ZIPS[y][1] for y in years)
        print(f"[kgs] dry-run. index: {INDEX_ZIP}")
        for y in years:
            sz, cnt = ARCHIVE_ZIPS[y]
            print(f"[kgs]   archive: {ARCHIVE_BASE}{y}  ({sz}, {cnt} files)")
        print(f"[kgs] planned LAS files across {len(years)} archives: ~{planned}")
        return FetchLog()

    index_file = fetch_index(raw_root)
    header, rows = parse_index(index_file)
    more = "..." if len(header) > 8 else ""
    print(f"[kgs] index: {len(rows)} well records, columns={header[:8]}{more}")
    if index_only:
        return FetchLog()

    log = fetch_archives(years, raw_root)
    unpack_las(raw_root)
    return log


def main() -> None:
    ap = argparse.ArgumentParser(description="KGS (Kansas) LAS ingester.")
    ap.add_argument("--raw-root", default="data/raw")
    ap.add_argument("--years", nargs="*", default=None,
                    help=f"Archive zips to fetch (default G1 subset: {RECOMMENDED_G1_YEARS}).")
    ap.add_argument("--index-only", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    ingest(raw_root=args.raw_root, years=args.years,
           index_only=args.index_only, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
