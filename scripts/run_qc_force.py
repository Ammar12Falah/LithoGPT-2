"""Full FORCE 2020 QC pass (WO-01 Task C).

Harmonizes the FORCE training wells (from train.zip, 98 training wells; the 10
open-leaderboard and 10 blind-final test wells are NOT touched), runs the
six-step QC suite per well, and writes:

    data/processed/force2020/<well>.parquet   depth + canonical + masks + BS aux
    reports/force2020_qc_records.csv          per-well QC record (all six steps)
    reports/unmapped_mnemonics.csv            aggregated unmapped (BS now gone)
    reports/qc_force2020/coverage_heatmap.png curve coverage across wells
    reports/qc_force2020/depth_hist.png        depth-coverage histogram
    reports/qc_force2020/washout_summary.png   washout interval per well
    reports/qc_force2020/index.html            dashboard index
    configs/force2020/norm_stats.json          PROVISIONAL, train-only

Usage:  python scripts/run_qc_force.py [--max-wells N]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

def _repo_root() -> Path:
    # Path(__file__) works when run as a file (python / %run / !python). A pasted
    # Jupyter cell has no __file__, so fall back to searching cwd upward for the
    # repo root. Run scripts as files, not by pasting the body into a cell.
    try:
        return Path(__file__).resolve().parents[1]
    except NameError:
        here = Path.cwd().resolve()
        for cand in (here, *here.parents):
            if (cand / "src" / "lithogpt2").is_dir():
                return cand
        return here


_ROOT = _repo_root()
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT / "scripts"))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from harmonize_force_demo import ensure_train_csv  # noqa: E402

from lithogpt2.config import HarmonizationConfig  # noqa: E402
from lithogpt2.ingest.force2020 import SOURCE, iter_force_wells  # noqa: E402
from lithogpt2.pipeline.harmonize import (  # noqa: E402
    compute_norm_stats,
    harmonize_well,
    write_unmapped_csv,
)
from lithogpt2.pipeline.qc import run_well_qc  # noqa: E402


def _dashboard(records, coverage_df, config, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    curves = list(config.canonical_curves)
    wells = [r.well_id for r in records]

    # Coverage heatmap (valid metres per curve per well).
    mat = np.array([[coverage_df.loc[w, f"cov_m_{c}"] for c in curves] for w in wells])
    fig, ax = plt.subplots(figsize=(max(6, len(curves) * 0.7), max(4, len(wells) * 0.25)))
    im = ax.imshow(mat, aspect="auto", cmap="viridis")
    ax.set_xticks(range(len(curves)), curves, rotation=45, ha="right")
    ax.set_yticks(range(len(wells)), wells, fontsize=6)
    ax.set_title("FORCE 2020 curve coverage (valid metres)")
    fig.colorbar(im, ax=ax, label="metres")
    fig.tight_layout()
    fig.savefig(out_dir / "coverage_heatmap.png", dpi=120)
    plt.close(fig)

    # Depth-coverage histogram (grid length in metres per well).
    lengths = [r.n_grid * config.grid_step_m for r in records]
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.hist(lengths, bins=20, color="#4c78a8")
    ax.set_xlabel("logged interval (m)")
    ax.set_ylabel("wells")
    ax.set_title("FORCE 2020 depth coverage")
    fig.tight_layout()
    fig.savefig(out_dir / "depth_hist.png", dpi=120)
    plt.close(fig)

    # Washout interval per well.
    wm = [r.washout_interval_m for r in records]
    fig, ax = plt.subplots(figsize=(max(6, len(wells) * 0.22), 4))
    ax.bar(range(len(wells)), wm, color="#e45756")
    ax.set_xticks(range(len(wells)), wells, rotation=90, fontsize=6)
    ax.set_ylabel("washout interval (m)")
    ax.set_title("FORCE 2020 washout coverage (CALI - BS > threshold)")
    fig.tight_layout()
    fig.savefig(out_dir / "washout_summary.png", dpi=120)
    plt.close(fig)

    n = len(records)
    passed = sum(1 for r in records if r.min_interval_pass)
    no_bs = sum(1 for r in records if r.no_bitsize)
    washed = sum(1 for r in records if r.washout_flagged and r.washout_interval_m > 0)
    html = f"""<!doctype html><html><head><meta charset="utf-8">
<title>FORCE 2020 QC dashboard</title>
<style>body{{background:#111;color:#eee;font-family:system-ui,sans-serif;margin:2rem}}
img{{max-width:100%;background:#fff;border-radius:8px;margin:1rem 0}}
.k{{color:#8ab4f8}}</style></head><body>
<h1>FORCE 2020 QC dashboard</h1>
<p>Wells processed: <span class="k">{n}</span> (FORCE training split only).
Passed minimum-interval: <span class="k">{passed}/{n}</span>.
Wells with washout flagging: <span class="k">{washed}</span>.
Wells with no bit size (washout skipped): <span class="k">{no_bs}</span>.</p>
<h2>Curve coverage</h2><img src="coverage_heatmap.png">
<h2>Depth coverage</h2><img src="depth_hist.png">
<h2>Washout coverage</h2><img src="washout_summary.png">
<p>Per-well records: reports/force2020_qc_records.csv</p>
</body></html>"""
    (out_dir / "index.html").write_text(html, encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--train-csv", default=None)
    ap.add_argument("--raw-root", default="data/raw")
    ap.add_argument("--max-wells", type=int, default=None)
    args = ap.parse_args()

    csv_path = Path(args.train_csv) if args.train_csv else ensure_train_csv(args.raw_root)
    config = HarmonizationConfig.load()
    out_dir = Path("data/processed") / SOURCE
    out_dir.mkdir(parents=True, exist_ok=True)

    # Fresh unmapped log so BS removal is visible.
    Path("reports").mkdir(exist_ok=True)
    unmapped_path = Path("reports/unmapped_mnemonics.csv")
    if unmapped_path.exists():
        unmapped_path.unlink()

    harmonized = []
    records = []
    unmapped_records: list[tuple[str, str, str, str]] = []
    coverage_rows = []

    for well_id, raw in iter_force_wells(str(csv_path), max_wells=args.max_wells):
        hw = harmonize_well(raw, config)
        rec = run_well_qc(hw, config)  # mutates hw (Hampel) before we persist
        harmonized.append(hw)
        records.append(rec)

        df = pd.DataFrame({"depth_m": hw.depth_m})
        for c in config.canonical_curves:
            df[c] = hw.curves[c]
            df[f"{c}_mask"] = hw.masks[c]
        for a in config.auxiliary_curves():
            df[a] = hw.aux_curves[a]
            df[f"{a}_mask"] = hw.aux_masks[a]
        safe = well_id.replace("/", "_").replace(" ", "_")
        df.to_parquet(out_dir / f"{safe}.parquet", index=False)

        for mnem, unit in hw.unmapped:
            unmapped_records.append((SOURCE, well_id, mnem, unit))

        crow = {"well_id": well_id}
        for c in config.canonical_curves:
            crow[f"cov_m_{c}"] = round(hw.curve_coverage_m(c), 1)
        coverage_rows.append(crow)

    write_unmapped_csv(unmapped_records, unmapped_path)
    pd.DataFrame([r.as_row() for r in records]).to_csv(
        "reports/force2020_qc_records.csv", index=False
    )
    coverage_df = pd.DataFrame(coverage_rows).set_index("well_id")
    _dashboard(records, coverage_df, config, Path("reports/qc_force2020"))

    # Provisional, train-only normalization stats.
    stats = compute_norm_stats(harmonized, config)
    with open("configs/force2020/norm_stats.json", "w", encoding="utf-8") as fh:
        json.dump(
            {
                "provisional": True,
                "provenance": (
                    f"PROVISIONAL. Computed on {len(harmonized)} FORCE-only wells "
                    "from train.zip (training split only; the 10 open-leaderboard "
                    "and 10 blind-final test wells were not read). Superseded at "
                    "Gate G2 by stats recomputed on the frozen multi-basin "
                    "training split."
                ),
                "config_version": config.version,
                "n_wells": len(harmonized),
                "stats": stats,
            },
            fh,
            indent=2,
        )

    n = len(records)
    passed = sum(1 for r in records if r.min_interval_pass)
    no_bs = sum(1 for r in records if r.no_bitsize)
    washed = sum(1 for r in records if r.washout_flagged and r.washout_interval_m > 0)
    distinct_unmapped = sorted({m for _, _, m, _ in unmapped_records})
    print(f"QC pass complete: {n} FORCE training wells.")
    print(f"  minimum-interval pass: {passed}/{n}")
    print(f"  washout flagged (BS present, washed intervals): {washed}")
    print(f"  no bit size (washout skipped): {no_bs}")
    print(f"  distinct unmapped mnemonics: {distinct_unmapped}")
    print("  dashboard: reports/qc_force2020/index.html")


if __name__ == "__main__":
    main()
