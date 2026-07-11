"""NLOG (Netherlands) ingester (handoff Section 6, G2 Task A).

NLOG is the Dutch subsurface portal run by TNO for the Ministry of Economic
Affairs. Administrative borehole data is public immediately; well logs
(LAS/DLIS) are released after a statutory five-year confidentiality period.
License: NLOG's own terms permit copying, downloading and redistribution with
attribution (see docs/LICENSE_MATRIX.md).

Access chain, every hop verified live against the server on 6 July 2026 by
reading the mapviewer app bundle and probing the endpoints (see
docs/NLOG_ACCESS.md for the capture):

  1. Borehole index: WFS GetFeature on nlog:gdw_ng_wll_all_utm returns every
     borehole with PUBLIC_AS_OF (release date) and a URL field ending in the
     internal mapviewer id, e.g. .../nlog-mapviewer/brh/106511838.
  2. Log file list, per borehole:
        POST /nlog-mapviewer/rest/brh/logdocuments
        body = the bare mapviewer id as a JSON string, e.g. "106511838"
     returns a JSON list, each entry: fileName, documentBfileDbk (download key),
     fileTypeCode (LAS/DLIS/...), fileSize, topDepth, bottomDepth, documentGroup.
  3. File bytes:
        GET /nlog-mapviewer/rest/brh/logdocument/{documentBfileDbk}
     returns application/octet-stream (a LAS begins "~Version Information").

So the whole corpus is programmatic: no DevTools capture and no hand-copied
per-borehole URLs. build_index() writes the released-borehole list;
resolve_log_documents() turns it into a per-file download index; and
ingest_from_index() fetches the bytes under the polite, resumable fetcher.

Expected wall-clock is HOURS: thousands of boreholes at one request per two
seconds for the logdocuments call, then one download per file. State the
estimate before launch and run it as a resumable background job with a monitor.
"""

from __future__ import annotations

import argparse
import csv
import json
import time
import urllib.error
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
LOGDOCS_URL = "https://www.nlog.nl/nlog-mapviewer/rest/brh/logdocuments"
DOWNLOAD_BASE = "https://www.nlog.nl/nlog-mapviewer/rest/brh/logdocument/"
TERMS_URL = "https://www.nlog.nl/en/data"

# File types we harmonize. LAS goes straight to the LAS reader; DLIS goes
# through dlisio (see io/dlis.py). Everything else (ASC, PDF, TIFF scans, ...)
# is skipped for modeling.
DEFAULT_FILE_TYPES = ("LAS", "DLIS")

_EXT = {"LAS": "las", "DLIS": "dlis"}

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

DOC_FIELDS = [
    "well_id",
    "mapviewer_id",
    "file_id",
    "file_name",
    "file_type",
    "file_size",
    "top_depth",
    "bottom_depth",
    "document_group",
    "download_url",
]

_MIN_INTERVAL_S = 2.0  # per-host spacing for the logdocuments API, matches _http


# --------------------------------------------------------------------------- #
# Step 1: borehole index from the WFS
# --------------------------------------------------------------------------- #
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
    """Build a released-borehole index CSV from the NLOG WFS. Returns row count."""
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
            mvid = _mapviewer_id(p.get("URL"))
            if not mvid:
                continue  # cannot resolve documents without the mapviewer id
            geom = feat.get("geometry") or {}
            coords = geom.get("coordinates") or [None, None]
            writer.writerow(
                {
                    "well_id": p.get("BOREHOLE_CODE") or mvid,
                    "borehole_name": p.get("BOREHOLE_NAME") or "",
                    "uwi": p.get("UWI") or "",
                    "nitg_number": p.get("NITG_NUMBER") or "",
                    "mapviewer_id": mvid,
                    "public_as_of": p.get("PUBLIC_AS_OF") or "",
                    "on_offshore": p.get("ON_OFFSHORE_CODE") or "",
                    "lon": coords[0],
                    "lat": coords[1],
                    "detail_url": p.get("URL") or "",
                }
            )
            n += 1
    print(f"[nlog] wrote {n} released boreholes to {out_csv} (released_only={released_only})")
    return n


# --------------------------------------------------------------------------- #
# Step 2: per-borehole log-document list (verified endpoint)
# --------------------------------------------------------------------------- #
def _post_logdocuments(
    mapviewer_id: str, timeout: int = 60, max_retries: int = 3, backoff_base_s: float = 2.0
) -> list[dict]:
    """POST one mapviewer id to the logdocuments endpoint, return the JSON list.

    The body is the bare id as a JSON string (the array and object forms both
    return 400; the raw string returns 200). Retries transient errors (429, 5xx,
    transport) with exponential backoff; a 4xx client error is not retried.
    Raises the last error if all attempts fail so the caller records it verbatim.
    """
    body = json.dumps(mapviewer_id).encode("utf-8")  # -> "106511838"
    req = urllib.request.Request(  # noqa: S310
        LOGDOCS_URL,
        data=body,
        method="POST",
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
    )
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
                payload = json.load(resp)
            if isinstance(payload, dict):
                payload = payload.get("documents") or payload.get("logDocuments") or []
            return payload if isinstance(payload, list) else []
        except urllib.error.HTTPError as exc:
            last_exc = exc
            if exc.code in (400, 401, 403, 404, 405, 410):
                raise
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            last_exc = exc
        if attempt < max_retries:
            time.sleep(backoff_base_s * (2**attempt))
    raise last_exc if last_exc else RuntimeError("logdocuments failed")


def _done_ids(out_csv: Path) -> set[str]:
    if not out_csv.exists():
        return set()
    done: set[str] = set()
    with out_csv.open("r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            if row.get("mapviewer_id"):
                done.add(row["mapviewer_id"])
    return done


def resolve_log_documents(
    index_csv: str,
    out_csv: str,
    file_types: tuple[str, ...] = DEFAULT_FILE_TYPES,
    max_boreholes: int | None = None,
) -> int:
    """Resolve per-borehole log files into a download index. Returns file rows.

    Reads the borehole index (needs mapviewer_id), POSTs each id to the
    logdocuments endpoint, keeps entries whose fileTypeCode is in ``file_types``,
    and appends rows to ``out_csv`` with a ready download_url. Resumable: a
    mapviewer id already present in ``out_csv`` is skipped, and the API is
    throttled to one call per two seconds. Failures are printed verbatim and do
    not abort the run.
    """
    index_path = Path(index_csv)
    if not index_path.exists():
        raise FileNotFoundError(
            f"NLOG borehole index not found: {index_csv}. Run build_index first."
        )
    out_path = Path(out_csv)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    keep = {t.upper() for t in file_types}
    done = _done_ids(out_path)

    with index_path.open("r", encoding="utf-8", newline="") as fh:
        boreholes = [r for r in csv.DictReader(fh) if r.get("mapviewer_id")]
    pending = [r for r in boreholes if r["mapviewer_id"] not in done]
    if max_boreholes is not None:
        pending = pending[:max_boreholes]

    new_file = not out_path.exists()
    written = 0
    n_with_logs = 0
    t0 = time.time()
    with out_path.open("a", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=DOC_FIELDS)
        if new_file:
            writer.writeheader()
        for i, row in enumerate(pending, 1):
            mvid = row["mapviewer_id"]
            well_id = row.get("well_id") or mvid
            time.sleep(_MIN_INTERVAL_S)
            try:
                docs = _post_logdocuments(mvid)
            except (
                urllib.error.URLError,
                urllib.error.HTTPError,
                TimeoutError,
                OSError,
                ValueError,
                json.JSONDecodeError,
            ) as exc:
                print(
                    f"[nlog] FAILED logdocuments {well_id} (id {mvid}): "
                    f"{type(exc).__name__}: {exc}",
                    flush=True,
                )
                continue
            kept = [d for d in docs if str(d.get("fileTypeCode", "")).upper() in keep]
            if kept:
                n_with_logs += 1
            for d in kept:
                fid = d.get("documentBfileDbk")
                if fid is None:
                    continue
                writer.writerow(
                    {
                        "well_id": well_id,
                        "mapviewer_id": mvid,
                        "file_id": fid,
                        "file_name": d.get("fileName") or "",
                        "file_type": str(d.get("fileTypeCode", "")).upper(),
                        "file_size": d.get("fileSize") or "",
                        "top_depth": d.get("topDepth"),
                        "bottom_depth": d.get("bottomDepth"),
                        "document_group": d.get("documentGroup") or "",
                        "download_url": f"{DOWNLOAD_BASE}{fid}",
                    }
                )
                written += 1
            if i % 100 == 0 or i == len(pending):
                fh.flush()
                rate = i / max(1e-9, time.time() - t0)
                eta = (len(pending) - i) / rate / 60 if rate else 0
                print(
                    f"[nlog] logdocuments {i}/{len(pending)} boreholes, "
                    f"{n_with_logs} with logs, {written} files, ~{eta:.0f} min left",
                    flush=True,
                )
    print(
        f"[nlog] resolved {written} downloadable files "
        f"({', '.join(sorted(keep))}) from {len(pending)} boreholes -> {out_csv}"
    )
    return written


# --------------------------------------------------------------------------- #
# Step 3: download the bytes
# --------------------------------------------------------------------------- #
def ingest_from_index(index_csv: str, raw_root: str = "data/raw") -> FetchLog:
    """Download every file in a resolved document index (from resolve_log_documents).

    Saves to data/raw/nlog/wells/{well_id}__{file_id}.{ext}, so a borehole's
    files share its code prefix and the QC iterator can group them. Resumable
    via the fetcher's manifest and throttled to one request per two seconds.
    """
    fetcher = PoliteFetcher(SOURCE, raw_root=raw_root)
    log = FetchLog()
    index_path = Path(index_csv)
    if not index_path.exists():
        raise FileNotFoundError(
            f"NLOG document index not found: {index_csv}. Build the borehole "
            f"index, then resolve_log_documents first (terms: {TERMS_URL})."
        )
    with index_path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        cols = reader.fieldnames or []
        if "download_url" not in cols:
            raise ValueError(
                "Index has no 'download_url' column. This looks like the raw "
                "borehole index; run resolve_log_documents first."
            )
        n = 0
        for row in reader:
            url = (row.get("download_url") or "").strip()
            well_id = (row.get("well_id") or "").strip()
            fid = (row.get("file_id") or "").strip()
            ext = _EXT.get((row.get("file_type") or "").upper(), "bin")
            if not url or not well_id or not fid:
                continue
            n += 1
            fetcher.fetch(url, rel_path=f"wells/{well_id}__{fid}.{ext}", log=log)
    print(
        f"[nlog] indexed={n} ok={len(log.ok)} skipped={len(log.skipped)} failed={len(log.failed)}"
    )
    for url, err in log.failed[:50]:
        print(f"[nlog] FAILED {url}: {err}")
    return log


# --------------------------------------------------------------------------- #
def main() -> None:
    ap = argparse.ArgumentParser(description="NLOG ingester (build-index -> resolve -> fetch).")
    sub = ap.add_subparsers(dest="cmd", required=True)

    bi = sub.add_parser("build-index", help="Build the released-borehole index from the WFS.")
    bi.add_argument("--out-csv", default="data/raw/nlog/borehole_index.csv")
    bi.add_argument("--all", action="store_true", help="Include not-yet-released boreholes too.")
    bi.add_argument("--onshore-only", action="store_true")

    rs = sub.add_parser("resolve", help="Resolve per-borehole log files into a download index.")
    rs.add_argument("--index-csv", default="data/raw/nlog/borehole_index.csv")
    rs.add_argument("--out-csv", default="data/raw/nlog/log_index.csv")
    rs.add_argument("--file-types", default="LAS,DLIS")
    rs.add_argument("--max-boreholes", type=int, default=None)

    fx = sub.add_parser("fetch", help="Download files from a resolved log index.")
    fx.add_argument("--index-csv", default="data/raw/nlog/log_index.csv")
    fx.add_argument("--raw-root", default="data/raw")

    args = ap.parse_args()
    if args.cmd == "build-index":
        build_index(args.out_csv, released_only=not args.all, onshore_only=args.onshore_only)
    elif args.cmd == "resolve":
        types = tuple(t.strip().upper() for t in args.file_types.split(",") if t.strip())
        resolve_log_documents(
            args.index_csv, args.out_csv, file_types=types, max_boreholes=args.max_boreholes
        )
    elif args.cmd == "fetch":
        ingest_from_index(args.index_csv, raw_root=args.raw_root)


if __name__ == "__main__":
    main()
