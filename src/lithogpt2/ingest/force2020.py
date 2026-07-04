"""FORCE 2020 ingester (handoff Section 4.1, Week 1 Task 3).

Authoritative source (verified 4 July 2026, counts confirmed against the real
files; see docs/LICENSE_MATRIX.md and configs/force2020/pinned.json):

  Labelled competition CSVs live in the FORCE GitHub repo under
  lithology_competition/data/ (raw.githubusercontent.com, no robots
  restriction). These carry the WELL column and the
  FORCE_2020_LITHOFACIES_LITHOLOGY label used for scoring:
    - train.zip            -> train.csv, 98 wells, 1,170,511 rows (VERIFIED)
    - leaderboard_test_features.csv  open test, 10 wells (VERIFIED)
    - leaderboard_test_target.csv    open-test labels
    - hidden_test.csv       10 wells
    - penalty_matrix.npy    official scoring matrix (also pinned in configs/)

  Logs are NLOD 2.0; lithofacies labels are CC-BY-4.0 (attribution: Bormann
  et al. 2020, FORCE Machine Learning Contest).

  A LAS-format mirror plus NPD spreadsheets is on Zenodo record 4351156
  (DOI 10.5281/zenodo.4351156). Zenodo's robots.txt blocks automated fetches
  of the file endpoints, so the LAS path is opt-in (--with-las) and runs the
  fetcher with robots checking disabled, which is appropriate for a direct,
  user-initiated download of a specific dataset by DOI (robots governs
  crawling and indexing, not dataset retrieval). It is not needed for the
  benchmark, which uses the CSVs above.

This ingester downloads the CSVs, unzips the training file, then VERIFIES the
well counts from the WELL column before anything downstream. On a count
mismatch it stops and reports rather than proceeding (handoff Rule 1).
"""

from __future__ import annotations

import argparse
import csv
import json
import urllib.request
import zipfile
from pathlib import Path

from . import USER_AGENT
from ._http import FetchLog, PoliteFetcher

SOURCE = "force2020"

# Authoritative labelled competition data (raw GitHub, no robots restriction).
GH_RAW = (
    "https://raw.githubusercontent.com/bolgebrygg/"
    "Force-2020-Machine-Learning-competition/master/lithology_competition/data/"
)
GH_FILES = [
    "train.zip",
    "leaderboard_test_features.csv",
    "leaderboard_test_target.csv",
    "hidden_test.csv",
    "penalty_matrix.npy",
]

# Optional LAS-format mirror (opt-in; robots disabled for direct DOI download).
ZENODO_RECORD = "4351156"
ZENODO_API = f"https://zenodo.org/api/records/{ZENODO_RECORD}"

EXPECTED = {"train_wells": 98, "open_test_wells": 10}


def count_wells(csv_path: Path, delimiter: str = ";") -> tuple[int, int]:
    """Count (unique wells, data rows) from the WELL column. Streaming."""
    wells: set[str] = set()
    rows = 0
    with csv_path.open("r", encoding="utf-8", newline="") as fh:
        header = fh.readline().rstrip("\n").split(delimiter)
        if "WELL" not in header:
            raise ValueError(f"No WELL column in {csv_path.name} (header={header[:6]})")
        widx = header.index("WELL")
        for line in fh:
            if not line.strip():
                continue
            rows += 1
            parts = line.rstrip("\n").split(delimiter)
            if widx < len(parts):
                wells.add(parts[widx])
    return len(wells), rows


def _unzip_train(dest_dir: Path) -> Path | None:
    """Extract train.csv from train.zip if present. Returns the CSV path."""
    zpath = dest_dir / "train.zip"
    if not zpath.exists():
        return None
    with zipfile.ZipFile(zpath) as zf:
        members = [n for n in zf.namelist() if n.lower().endswith(".csv")]
        if not members:
            return None
        target = members[0]
        zf.extract(target, dest_dir)
        return dest_dir / target


def resolve_zenodo_files() -> list[dict]:
    """Return the Zenodo LAS-mirror file list (opt-in path)."""
    req = urllib.request.Request(ZENODO_API, headers={"User-Agent": USER_AGENT})  # noqa: S310
    with urllib.request.urlopen(req, timeout=120) as resp:  # noqa: S310
        record = json.load(resp)
    return [
        {"key": f.get("key"), "url": f.get("links", {}).get("self")}
        for f in record.get("files", [])
    ]


def ingest(
    raw_root: str = "data/raw",
    dry_run: bool = False,
    with_las: bool = False,
) -> FetchLog:
    """Download FORCE 2020, verify counts, return the fetch log."""
    fetcher = PoliteFetcher(SOURCE, raw_root=raw_root)
    log = FetchLog()
    dest = Path(raw_root) / SOURCE

    if dry_run:
        print("[force2020] dry-run. Would fetch from GitHub raw:")
        for f in GH_FILES:
            print(f"[force2020]   {GH_RAW}{f}")
        if with_las:
            print(f"[force2020] and resolve LAS mirror from {ZENODO_API}")
        return log

    for f in GH_FILES:
        fetcher.fetch(GH_RAW + f, rel_path=f, log=log)

    train_csv = _unzip_train(dest)

    # Verify counts (handoff Rule 1: stop on mismatch, do not proceed silently).
    checks: list[tuple[str, int, int | None]] = []
    if train_csv is not None and train_csv.exists():
        w, r = count_wells(train_csv)
        print(f"[force2020] train.csv: {w} wells, {r} rows")
        checks.append(("train_wells", w, EXPECTED["train_wells"]))
    open_test = dest / "leaderboard_test_features.csv"
    if open_test.exists():
        w, r = count_wells(open_test)
        print(f"[force2020] leaderboard_test_features.csv: {w} wells, {r} rows")
        checks.append(("open_test_wells", w, EXPECTED["open_test_wells"]))

    if with_las:
        las = PoliteFetcher(SOURCE, raw_root=raw_root, respect_robots=False)
        for f in resolve_zenodo_files():
            if f["url"] and f["key"]:
                las.fetch(f["url"], rel_path=f"las/{f['key']}", log=log)

    print(f"[force2020] ok={len(log.ok)} skipped={len(log.skipped)} failed={len(log.failed)}")
    for url, err in log.failed:
        print(f"[force2020] FAILED {url}: {err}")

    mism = [(k, got, exp) for k, got, exp in checks if exp is not None and got != exp]
    if mism:
        for k, got, exp in mism:
            print(f"[force2020] COUNT MISMATCH {k}: got {got}, expected {exp}. STOPPING.")
        raise SystemExit(1)
    if checks:
        print("[force2020] counts verified against EXPECTED. OK.")
    return log


# FORCE column units (FORCE 2020 conventions) for the RawWell adapter. Columns
# not listed and not in FORCE_NONCURVE are still passed with unit "" so the
# harmonizer logs them as unmapped for triage rather than dropping silently.
FORCE_CURVE_UNITS = {
    "CALI": "in", "BS": "in", "DCAL": "in",
    "RSHA": "ohm.m", "RMED": "ohm.m", "RDEP": "ohm.m", "RMIC": "ohm.m", "RXO": "ohm.m",
    "RHOB": "g/cm3", "DRHO": "g/cm3",
    "GR": "gAPI", "SGR": "gAPI",
    "NPHI": "v/v", "PEF": "b/e",
    "DTC": "us/ft", "DTS": "us/ft",
    "SP": "mV",
}
FORCE_NONCURVE = frozenset(
    {
        "WELL", "DEPTH_MD", "X_LOC", "Y_LOC", "Z_LOC", "GROUP", "FORMATION",
        "FORCE_2020_LITHOFACIES_LITHOLOGY", "FORCE_2020_LITHOFACIES_CONFIDENCE",
    }
)


def iter_force_wells(train_csv: str, max_wells: int | None = None):
    """Yield (well_id, RawWell) per WELL from a FORCE CSV (semicolon-delimited).

    DEPTH_MD is the depth index in metres. Each non-administrative column is a
    raw curve keyed by its FORCE name so harmonize.py owns the alias mapping.
    Wells are contiguous in the FORCE files, so this streams and can stop early.
    """
    import numpy as np

    from ..io.las import RawCurve, RawWell

    def _f(s: str) -> float:
        s = s.strip()
        if not s:
            return float("nan")
        try:
            return float(s)
        except ValueError:
            return float("nan")

    with open(train_csv, encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh, delimiter=";")
        header = next(reader)
        idx = {name: i for i, name in enumerate(header)}
        if "WELL" not in idx or "DEPTH_MD" not in idx:
            raise ValueError("FORCE CSV missing WELL or DEPTH_MD column")
        widx, didx = idx["WELL"], idx["DEPTH_MD"]
        curve_cols = [c for c in header if c not in FORCE_NONCURVE]

        def build(well_id: str, rows: list[list[str]]) -> RawWell:
            depth = np.array([_f(r[didx]) for r in rows], dtype=float)
            curves: dict[str, RawCurve] = {}
            for c in curve_cols:
                ci = idx[c]
                data = np.array([_f(r[ci]) if ci < len(r) else float("nan") for r in rows])
                if np.all(np.isnan(data)):
                    continue  # curve absent for this well
                curves[c] = RawCurve(mnemonic=c, unit=FORCE_CURVE_UNITS.get(c, ""), data=data)
            return RawWell(
                well_id=well_id, source=SOURCE, depth=depth, depth_unit="m",
                curves=curves, path=None, header={},
            )

        cur: str | None = None
        rows: list[list[str]] = []
        count = 0
        for row in reader:
            if not row:
                continue
            w = row[widx]
            if cur is None:
                cur = w
            if w != cur:
                yield cur, build(cur, rows)
                count += 1
                rows = []
                cur = w
                if max_wells is not None and count >= max_wells:
                    return
            rows.append(row)
        if rows and (max_wells is None or count < max_wells):
            yield cur, build(cur, rows)


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingest FORCE 2020 well-log dataset.")
    ap.add_argument("--raw-root", default="data/raw")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--with-las", action="store_true", help="also fetch the Zenodo LAS mirror")
    args = ap.parse_args()
    ingest(raw_root=args.raw_root, dry_run=args.dry_run, with_las=args.with_las)


if __name__ == "__main__":
    main()
