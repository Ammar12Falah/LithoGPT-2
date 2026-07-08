"""NLOG harmonize + QC pass, chunked and resumable (LAS + DLIS).

One RawWell per borehole (richest file), so QC-passing counts are boreholes,
not files. Mirrors run_qc_kgs.py: resumable via the records file, non-fatal
dashboard, verbatim failures.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path


def _repo_root() -> Path:
    try:
        return Path(__file__).resolve().parents[1]
    except NameError:
        here = Path.cwd().resolve()
        for cand in (here, *here.parents):
            if (cand / "src" / "lithogpt2").is_dir():
                return cand
        return here


sys.path.insert(0, str(_repo_root() / "src"))

from lithogpt2.config import HarmonizationConfig  # noqa: E402
from lithogpt2.ingest.well_dir import iter_nlog_wells  # noqa: E402
from lithogpt2.pipeline.batch import build_dashboard, run_batch  # noqa: E402
from lithogpt2.pipeline.incremental import (  # noqa: E402
    done_well_ids, merge_keyed, merge_unmapped, records_from_df,
)

SOURCE = "nlog"
REPORTS = Path("reports")


def _borehole_ids(well_dir: Path) -> list[str]:
    """Distinct borehole codes present as {code}__{file_id}.{ext} files."""
    exts = {".las", ".dlis"}
    ids = set()
    for p in well_dir.iterdir():
        if p.suffix.lower() in exts:
            stem = p.stem
            ids.add(stem.split("__", 1)[0] if "__" in stem else stem)
    return sorted(ids)


def _write_reports(rec_csv, cov_csv, unmapped_csv, fail_csv,
                   new_rec_rows, new_cov_rows, new_unmapped, new_fail_rows):
    rec_df = merge_keyed(rec_csv, new_rec_rows)
    cov_df = merge_keyed(cov_csv, new_cov_rows)
    unmapped_df = merge_unmapped(unmapped_csv, new_unmapped)
    fail_df = merge_keyed(fail_csv, new_fail_rows)
    rec_df.to_csv(rec_csv, index=False)
    cov_df.to_csv(cov_csv, index=False)
    unmapped_df.to_csv(unmapped_csv, index=False)
    fail_df.to_csv(fail_csv, index=False)
    return rec_df, cov_df, unmapped_df, fail_df


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--well-dir", default="data/raw/nlog/wells")
    ap.add_argument("--max-wells", type=int, default=None)
    ap.add_argument("--chunk", type=int, default=200)
    ap.add_argument("--fresh", action="store_true")
    ap.add_argument("--reprocess-ids-file", default=None,
                    help="newline-delimited borehole IDs to force-reprocess (fallback re-QC)")
    ap.add_argument("--no-parquet", action="store_true")
    args = ap.parse_args()

    well_dir = Path(args.well_dir)
    if not well_dir.exists() or not _borehole_ids(well_dir):
        print(f"No LAS/DLIS files in {well_dir}. Run the ingester first."); return

    REPORTS.mkdir(exist_ok=True)
    rec_csv = REPORTS / "nlog_qc_records.csv"
    cov_csv = REPORTS / "nlog_coverage.csv"
    unmapped_csv = REPORTS / "nlog_unmapped_mnemonics.csv"
    fail_csv = REPORTS / "nlog_failures.csv"
    processed_dir = None if args.no_parquet else Path("data/processed") / SOURCE
    config = HarmonizationConfig.load()

    all_ids = _borehole_ids(well_dir)
    done = set() if args.fresh else done_well_ids(rec_csv)
    if args.fresh:
        for f in (rec_csv, cov_csv, unmapped_csv, fail_csv):
            if f.exists():
                f.unlink()
    if args.reprocess_ids_file:
        from pathlib import Path as _P
        force = {ln.strip() for ln in _P(args.reprocess_ids_file).read_text(
            encoding="utf-8").splitlines() if ln.strip()}
        pending = [b for b in all_ids if b in force]
    else:
        pending = [b for b in all_ids if b not in done]
    if args.max_wells is not None:
        pending = pending[:args.max_wells]

    print(f"NLOG QC: {len(all_ids)} boreholes, {len(done)} already done, "
          f"{len(pending)} to process.", flush=True)
    if not pending:
        print("Nothing to process. Done."); return

    start, processed = time.time(), 0
    rec_df = unmapped_df = fail_df = None
    for i in range(0, len(pending), args.chunk):
        chunk = set(pending[i:i + args.chunk])
        skip = set(all_ids) - chunk
        read_failures: list[tuple[str, str]] = []
        wells = iter_nlog_wells(well_dir, SOURCE, read_failures, skip_ids=skip)
        result = run_batch(wells, config, SOURCE,
                           processed_dir=processed_dir, keep_harmonized=False)
        new_rec_rows = [r.as_row() for r in result["records"]]
        new_fail_rows = [{"well_id": w, "error": e}
                         for w, e in (read_failures + result["failures"])]
        rec_df, _, unmapped_df, fail_df = _write_reports(
            rec_csv, cov_csv, unmapped_csv, fail_csv,
            new_rec_rows, result["coverage"], result["unmapped"], new_fail_rows)
        processed += len(chunk)
        rate = processed / max(1e-9, time.time() - start)
        eta_min = ((len(pending) - processed) / rate) / 60 if rate else 0
        passing = int(rec_df["min_interval_pass"].sum()) if "min_interval_pass" in rec_df else 0
        print(f"  checkpoint: {processed}/{len(pending)} this run "
              f"(cumulative {len(rec_df)} boreholes, {passing} QC-passing, "
              f"{len(fail_df) if not fail_df.empty else 0} failed), "
              f"~{eta_min:.0f} min left", flush=True)

    try:
        dash_records = records_from_df(rec_df)
        cov_rows = merge_keyed(cov_csv, []).to_dict("records")
        build_dashboard(dash_records, cov_rows, config, REPORTS / "qc_nlog", title="NLOG")
        dash_note = "reports/qc_nlog/index.html"
    except Exception as e:  # noqa: BLE001
        dash_note = f"SKIPPED ({type(e).__name__}: {e}); CSVs are intact."

    total = len(rec_df)
    passing = int(rec_df["min_interval_pass"].sum()) if "min_interval_pass" in rec_df else 0
    distinct = len(unmapped_df) if unmapped_df is not None and not unmapped_df.empty else 0
    print(f"DONE. cumulative boreholes: {total}   QC-passing: {passing}/{total}")
    print(f"  distinct unmapped mnemonics: {distinct}")
    print(f"  records: {rec_csv}   dashboard: {dash_note}")


if __name__ == "__main__":
    main()
