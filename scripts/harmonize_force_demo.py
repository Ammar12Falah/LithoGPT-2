"""Harmonize real FORCE 2020 wells end to end and write processed artifacts.

Run where the FORCE train.zip is reachable (or pass an already-extracted CSV):

    python scripts/harmonize_force_demo.py --max-wells 12

Outputs (all real, artifact-backed):
    data/processed/force2020/<well>.parquet   depth_m + canonical curves + masks
    reports/unmapped_mnemonics.csv            aggregated raw mnemonics with no map
    reports/force2020_coverage.csv            per-well curve coverage + usability
    configs/force2020/norm_stats.json         median/IQR on these wells (train-split contract)
"""

from __future__ import annotations

import argparse
import io
import json
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd

from lithogpt2.config import HarmonizationConfig
from lithogpt2.ingest.force2020 import SOURCE, iter_force_wells
from lithogpt2.pipeline.harmonize import compute_norm_stats, harmonize_well, write_unmapped_csv

TRAIN_ZIP_URL = (
    "https://raw.githubusercontent.com/bolgebrygg/"
    "Force-2020-Machine-Learning-competition/master/lithology_competition/data/train.zip"
)


def ensure_train_csv(raw_root: str) -> Path:
    dest = Path(raw_root) / SOURCE
    dest.mkdir(parents=True, exist_ok=True)
    csv_path = dest / "train.csv"
    if csv_path.exists():
        return csv_path
    print(f"Downloading FORCE train.zip (~92 MB) from {TRAIN_ZIP_URL}")
    req = urllib.request.Request(TRAIN_ZIP_URL, headers={"User-Agent": "lithogpt2"})  # noqa: S310
    with urllib.request.urlopen(req, timeout=300) as resp:  # noqa: S310
        blob = resp.read()
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        name = next(n for n in zf.namelist() if n.lower().endswith(".csv"))
        zf.extract(name, dest)
        extracted = dest / name
        if extracted != csv_path:
            extracted.rename(csv_path)
    return csv_path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--train-csv", default=None, help="Path to FORCE train.csv")
    ap.add_argument("--raw-root", default="data/raw")
    ap.add_argument("--max-wells", type=int, default=12)
    args = ap.parse_args()

    csv_path = Path(args.train_csv) if args.train_csv else ensure_train_csv(args.raw_root)
    config = HarmonizationConfig.load()
    out_dir = Path("data/processed") / SOURCE
    out_dir.mkdir(parents=True, exist_ok=True)

    harmonized = []
    unmapped_records: list[tuple[str, str, str, str]] = []
    coverage_rows = []

    for well_id, raw in iter_force_wells(str(csv_path), max_wells=args.max_wells):
        hw = harmonize_well(raw, config)
        harmonized.append(hw)

        df = pd.DataFrame({"depth_m": hw.depth_m})
        for c in config.canonical_curves:
            df[c] = hw.curves[c]
            df[f"{c}_mask"] = hw.masks[c]
        safe = well_id.replace("/", "_").replace(" ", "_")
        df.to_parquet(out_dir / f"{safe}.parquet", index=False)

        for mnem, unit in hw.unmapped:
            unmapped_records.append((SOURCE, well_id, mnem, unit))

        row = {
            "well_id": well_id,
            "n_grid": int(hw.depth_m.size),
            "usable": hw.usable,
            "present": ",".join(hw.present_curves),
        }
        for c in config.canonical_curves:
            row[f"cov_m_{c}"] = round(hw.curve_coverage_m(c), 1)
        coverage_rows.append(row)

        cov = {c: round(hw.curve_coverage_m(c)) for c in hw.present_curves}
        print(f"{well_id:12s} grid={hw.depth_m.size:6d} usable={hw.usable!s:5s} "
              f"present={len(hw.present_curves):2d} coverage_m={cov}")

    Path("reports").mkdir(exist_ok=True)
    write_unmapped_csv(unmapped_records, "reports/unmapped_mnemonics.csv")
    pd.DataFrame(coverage_rows).to_csv("reports/force2020_coverage.csv", index=False)

    stats = compute_norm_stats(harmonized, config)
    with open("configs/force2020/norm_stats.json", "w", encoding="utf-8") as fh:
        json.dump({"config_version": config.version, "n_wells": len(harmonized),
                   "note": "median/IQR on these FORCE wells; train-split contract",
                   "stats": stats}, fh, indent=2)

    usable = sum(1 for h in harmonized if h.usable)
    n_unmapped = len({(m, u) for _, _, m, u in unmapped_records})
    print(f"\nHarmonized {len(harmonized)} wells, {usable} usable. "
          f"Distinct unmapped mnemonics: {n_unmapped}. "
          f"Norm stats over {len(stats)} curves.")


if __name__ == "__main__":
    main()
