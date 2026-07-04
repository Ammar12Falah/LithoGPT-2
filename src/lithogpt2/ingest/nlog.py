"""NLOG (Netherlands) ingester (handoff Section 4.1, Week 1 Task 5).

Verified 4 July 2026 (live data confirmed; see docs/NLOG_ACCESS.md and
docs/LICENSE_MATRIX.md). NLOG is the Dutch subsurface portal run by TNO for the
Ministry of Economic Affairs. Administrative borehole data is public
immediately; well logs (LIS/LAS/DLIS) are released after a statutory five-year
confidentiality period.

Borehole index (CONFIRMED, no scraping): NLOG's official GeoServer WFS.
  base   : https://www.gdngeoservices.nl/geoserver/nlog/ows
  layer  : nlog:gdw_ng_wll_all_utm   ("All boreholes")
  format : GeoJSON (outputFormat=json), WFS 1.0.0
One GetFeature call returns every borehole with attributes: BOREHOLE_CODE,
BOREHOLE_NAME, UWI, NITG_NUMBER, ON_OFFSHORE_CODE, PUBLIC_AS_OF (confidentiality
release date), and URL (the mapviewer detail link ending in a numeric borehole
id, e.g. .../nlog-mapviewer/brh/872287025). build_index() below turns this into
a well-list CSV and is fully runnable.

Per-borehole LAS resolution (ONE hop still to confirm, not guessed per handoff
Rule 2): the mapviewer/datacenter file-list API keyed by the numeric borehole
id, and the file-download URL it returns (NLOG files are named
NLOG_LIS_LAS_{fileid}_... and served by asset id). docs/NLOG_ACCESS.md has the
capture. Once confirmed, resolve_las_urls() is filled in and the existing
resumable fetch loop (ingest_from_index) runs the bulk job.

Expected wall-clock for a bulk NLOG run at one request / 2 s is HOURS. State the
estimate before launch and run it as a resumable background job.
"""

from __future__ import annotations

import argparse
import csv
import json
import urllib.parse
import urllib.request
from datetime import date, datetime
from pathlib import Path

from . import USER_AGENT
from ._http import FetchLog, PoliteFetcher

SOURCE = "nlog"

WFS_BASE = "https://www.gdngeoservices.nl/geoserver/nlog/ows"
WFS_LAYER = "nlog:gdw_ng_wll_all_utm"
MAPVIEWER = "https://www.nlog.nl/nlog-mapviewer/"
TERMS_URL = "https://www.nlog.nl/en/data"
DISCLAIMER_URL = "https://www.nlog.nl/en/disclaimer"

INDEX_FIELDS = [
    "well_id",
    "borehole_name",
    "uwi",
    "nitg_number",
    "mapviewer_id",
    "public_as_of",
    "on_offshore",
    "lon",
    "lat",
    "detail_url",
]


def fetch_borehole_geojson(srs: str = "EPSG:4326", timeout: int = 300) -> dict:
    """Fetch the full 'All boreholes' layer as GeoJSON from the NLOG WFS."""
    params = {
        "service": "WFS",
        "version": "1.0.0",
        "request": "GetFeature",
        "typeName": WFS_LAYER,
        "outputFormat": "json",
        "srsName": srs,
    }
    url = f"{WFS_BASE}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})  # noqa: S310
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return json.load(resp)


def _mapviewer_id(url: str | None) -> str:
    """Extract the trailing numeric borehole id from a mapviewer detail URL."""
    if not url:
        return ""
    return url.rstrip("/").rsplit("/", 1)[-1]


def _is_released(public_as_of: str | None, on: date) -> bool:
    """True if the borehole's confidentiality period has expired by ``on``."""
    if not public_as_of:
        return False
    try:
        return datetime.strptime(public_as_of[:10], "%Y-%m-%d").date() <= on
    except ValueError:
        return False


def build_index(
    out_csv: str,
    released_only: bool = True,
    onshore_only: bool = False,
    srs: str = "EPSG:4326",
) -> int:
    """Build a borehole index CSV from the NLOG WFS. Returns row count.

    Columns: well_id, borehole_name, uwi, nitg_number, mapviewer_id,
    public_as_of, on_offshore, lon, lat, detail_url. The LAS URL is NOT added
    here: it needs the per-borehole file-list API (see module docstring).
    """
    gj = fetch_borehole_geojson(srs=srs)
    today = date.today()
    out_path = Path(out_csv)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with out_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=INDEX_FIELDS)
        writer.writeheader()
        for feat in gj.get("features", []):
            p = feat.get("properties", {})
            if released_only and not _is_released(p.get("PUBLIC_AS_OF"), today):
                continue
            if onshore_only and p.get("ON_OFFSHORE_CODE") != "ON":
                continue
            geom = feat.get("geometry") or {}
            coords = geom.get("coordinates") or [None, None]
            writer.writerow(
                {
                    "well_id": p.get("BOREHOLE_CODE") or "",
                    "borehole_name": p.get("BOREHOLE_NAME") or "",
                    "uwi": p.get("UWI") or "",
                    "nitg_number": p.get("NITG_NUMBER") or "",
                    "mapviewer_id": _mapviewer_id(p.get("URL")),
                    "public_as_of": p.get("PUBLIC_AS_OF") or "",
                    "on_offshore": p.get("ON_OFFSHORE_CODE") or "",
                    "lon": coords[0],
                    "lat": coords[1],
                    "detail_url": p.get("URL") or "",
                }
            )
            n += 1
    print(f"[nlog] wrote {n} boreholes to {out_csv} (released_only={released_only})")
    return n


def resolve_las_urls(index_csv: str, out_csv: str) -> int:
    """Resolve per-borehole LAS download URLs from the file-list API.

    PENDING CONFIRMATION (handoff Rule 2): the mapviewer/datacenter file-list
    endpoint keyed by mapviewer_id, and the file-download URL it returns, are
    not yet pinned and must not be guessed. See docs/NLOG_ACCESS.md for the
    one-time capture. Once known, this reads the index (with mapviewer_id),
    queries the file list per borehole, filters to LAS, and writes an index CSV
    with columns well_id,las_url for ingest_from_index().
    """
    raise NotImplementedError(
        "NLOG LAS file-list API not yet confirmed. See docs/NLOG_ACCESS.md. "
        "Do not guess the endpoint (handoff Rule 2)."
    )


def ingest_from_index(index_csv: str, raw_root: str = "data/raw") -> FetchLog:
    """Fetch every LAS in a supplied index CSV (columns: well_id, las_url)."""
    fetcher = PoliteFetcher(SOURCE, raw_root=raw_root)
    log = FetchLog()
    index_path = Path(index_csv)
    if not index_path.exists():
        raise FileNotFoundError(
            f"NLOG index not found: {index_csv}. Build a borehole index with "
            f"build_index() first, then resolve LAS URLs (terms: {TERMS_URL})."
        )
    with index_path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        if "las_url" not in (reader.fieldnames or []):
            raise ValueError(
                "Index has no 'las_url' column. This is the borehole index from "
                "build_index(); resolve LAS URLs first (see docs/NLOG_ACCESS.md)."
            )
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
    ap = argparse.ArgumentParser(description="NLOG ingester.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    bi = sub.add_parser("build-index", help="Build a borehole index from the WFS.")
    bi.add_argument("--out-csv", default="data/raw/nlog/borehole_index.csv")
    bi.add_argument("--all", action="store_true", help="Include not-yet-released too.")
    bi.add_argument("--onshore-only", action="store_true")

    fx = sub.add_parser("fetch", help="Fetch LAS from an index with well_id,las_url.")
    fx.add_argument("--index-csv", required=True)
    fx.add_argument("--raw-root", default="data/raw")

    args = ap.parse_args()
    if args.cmd == "build-index":
        build_index(args.out_csv, released_only=not args.all, onshore_only=args.onshore_only)
    elif args.cmd == "fetch":
        ingest_from_index(args.index_csv, raw_root=args.raw_root)


if __name__ == "__main__":
    main()
