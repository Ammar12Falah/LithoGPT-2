"""KGS harmonize + QC pass, chunked and resumable."""
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
from lithogpt2.ingest.las_dir import iter_las_wells  # noqa: E402
from lithogpt2.pipeline.batch import build_dashboard, run_batch  # noqa: E402
from lithogpt2.pipeline.incremental import (  # noqa: E402
    done_well_ids, merge_keyed, merge_unmapped, records_from_df,
)

SOURCE = "kgs"
REPORTS = Path("reports")


def looks_like_las(path: Path, head_bytes: int = 8192, min_size: int = 200) -> bool:
    """True only for plausibly real LAS; rejects tiny files and non-LAS junk."""
    try:
        if path.stat().st_size < min_size:
            return False
        with open(path, "rb") as fh:
            head = fh.read(head_bytes).upper()
    except OSError:
        return False
    return (b"~V" in head) or (b"VERS" in head)


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
    ap.add_argument("--las-dir", default="data/raw/kgs/las")
    ap.add_argument("--max-wells", type=int, default=None)
    ap.add_argument("--chunk", type=int, default=200)
    ap.add_argument("--fresh", action="store_true")
    ap.add_argument("--no-parquet", action="store_true")
    args = ap.parse_args()

    las_dir = Path(args.las_dir)
    if not las_dir.exists() or not any(las_dir.glob("*.las")):
        print(f"No LAS files in {las_dir}. Run the ingester first."); return

    REPORTS.mkdir(exist_ok=True)
    rec_csv = REPORTS / "kgs_qc_records.csv"
    cov_csv = REPORTS / "kgs_coverage.csv"
    unmapped_csv = REPORTS / "kgs_unmapped_mnemonics.csv"
    fail_csv = REPORTS / "kgs_failures.csv"
    processed_dir = None if args.no_parquet else Path("data/processed") / SOURCE
    config = HarmonizationConfig.load()

    all_paths = sorted(las_dir.glob("*.las"))
    all_stems = {p.stem for p in all_paths}
    real = [p for p in all_paths if looks_like_las(p)]
    n_junk = len(all_paths) - len(real)
    done = set() if args.fresh else done_well_ids(rec_csv)
    pending = [p for p in real if p.stem not in done]
    if args.max_wells is not None:
        pending = pending[:args.max_wells]

    print(f"KGS QC: {len(all_paths)} files, {n_junk} skipped as non-LAS, "
          f"{len(done)} already done, {len(pending)} to process.", flush=True)
    if not pending:
        print("Nothing to process. Done."); return

    start, processed = time.time(), 0
    rec_df = unmapped_df = fail_df = None
    for i in range(0, len(pending), args.chunk):
        chunk = pending[i:i + args.chunk]
        skip = all_stems - {p.stem for p in chunk}
        read_failures: list[tuple[str, str]] = []
        wells = iter_las_wells(las_dir, SOURCE, read_failures, skip_stems=skip)
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
              f"(cumulative {len(rec_df)} wells, {passing} QC-passing, "
              f"{len(fail_df) if not fail_df.empty else 0} failed), "
              f"~{eta_min:.0f} min left", flush=True)

    try:
        dash_records = records_from_df(rec_df)
        cov_rows = merge_keyed(cov_csv, []).to_dict("records")
        build_dashboard(dash_records, cov_rows, config, REPORTS / "qc_kgs", title="KGS")
        dash_note = "reports/qc_kgs/index.html"
    except Exception as e:  # noqa: BLE001
        dash_note = f"SKIPPED ({type(e).__name__}: {e}); CSVs are intact."

    total = len(rec_df)
    passing = int(rec_df["min_interval_pass"].sum()) if "min_interval_pass" in rec_df else 0
    distinct = len(unmapped_df) if unmapped_df is not None and not unmapped_df.empty else 0
    print(f"DONE. cumulative wells: {total}   QC-passing: {passing}/{total}")
    print(f"  non-LAS skipped: {n_junk}   distinct unmapped mnemonics: {distinct}")
    print(f"  records: {rec_csv}   dashboard: {dash_note}")


if __name__ == "__main__":
    main()
