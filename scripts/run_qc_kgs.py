"""KGS harmonize + QC pass (runs after `python -m lithogpt2.ingest.kgs`).

Reads the unpacked KGS LAS files, harmonizes and QCs each through the same
engine used for FORCE, and writes:

    data/processed/kgs/<well>.parquet        depth + canonical + masks + BS aux
    reports/kgs_qc_records.csv               per-well QC record (six steps)
    reports/kgs_coverage.csv                 per-well curve coverage
    reports/kgs_unmapped_mnemonics.csv       unmapped mnemonics (triage)
    reports/kgs_failures.csv                 unreadable LAS files (with reason)
    reports/qc_kgs/index.html                dashboard

Usage:  python scripts/run_qc_kgs.py [--las-dir data/raw/kgs/las] [--max-wells N]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

import pandas as pd  # noqa: E402

from lithogpt2.config import HarmonizationConfig  # noqa: E402
from lithogpt2.ingest.las_dir import iter_las_wells  # noqa: E402
from lithogpt2.pipeline.batch import (  # noqa: E402
    build_dashboard,
    run_batch,
    write_source_reports,
)

SOURCE = "kgs"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--las-dir", default="data/raw/kgs/las")
    ap.add_argument("--max-wells", type=int, default=None)
    args = ap.parse_args()

    las_dir = Path(args.las_dir)
    if not las_dir.exists() or not any(las_dir.glob("*.las")):
        print(f"No LAS files in {las_dir}. Run the ingester first:")
        print("  python -m lithogpt2.ingest.kgs        # index + G1 subset + unpack")
        return

    config = HarmonizationConfig.load()
    failures: list[tuple[str, str]] = []
    wells = iter_las_wells(las_dir, SOURCE, failures, max_wells=args.max_wells)

    result = run_batch(
        wells, config, SOURCE,
        processed_dir=Path("data/processed") / SOURCE,
        keep_harmonized=False,
    )
    paths = write_source_reports(result, SOURCE, Path("reports"))
    build_dashboard(result["records"], result["coverage"], config,
                    Path("reports/qc_kgs"), title="KGS")

    # read failures include both LAS-read failures and per-well QC failures.
    all_failures = failures + result["failures"]
    pd.DataFrame(all_failures, columns=["well_id", "error"]).to_csv(
        "reports/kgs_failures.csv", index=False
    )

    recs = result["records"]
    n = len(recs)
    passing = sum(1 for r in recs if r.min_interval_pass)
    washed = sum(1 for r in recs if r.washout_flagged and r.washout_interval_m > 0)
    no_bs = sum(1 for r in recs if r.no_bitsize)
    distinct_unmapped = sorted({m for _, _, m, _ in result["unmapped"]})
    print(f"KGS QC pass: {n} wells harmonized, {len(all_failures)} unreadable/failed.")
    print(f"  minimum-interval pass (QC-passing): {passing}/{n}")
    print(f"  washout flagged: {washed}   no bit size: {no_bs}")
    print(f"  distinct unmapped mnemonics: {len(distinct_unmapped)} "
          f"(top: {distinct_unmapped[:15]})")
    print(f"  records: {paths['records']}   dashboard: reports/qc_kgs/index.html")


if __name__ == "__main__":
    main()
