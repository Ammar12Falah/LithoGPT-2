"""Shared harmonize + QC batch engine used by the per-source runners.

One code path so FORCE and KGS (and later NLOG) produce identical processed
parquet, per-well QC records, and dashboards. Memory-safe for large sources:
by default it does not retain HarmonizedWell objects, only the small per-well
records and coverage rows, so tens of thousands of wells stream through without
holding the whole corpus in RAM. Per-well failures are caught and recorded so a
single bad LAS never aborts a bulk run.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from pathlib import Path

import pandas as pd

from ..config import HarmonizationConfig
from ..io.las import RawWell
from .harmonize import HarmonizedWell, harmonize_well, write_unmapped_csv
from .qc import QCRecord, run_well_qc


def _safe(well_id: str) -> str:
    return well_id.replace("/", "_").replace(" ", "_").replace("\\", "_")


def write_processed_parquet(hw: HarmonizedWell, config: HarmonizationConfig, out_dir: Path) -> None:
    df = pd.DataFrame({"depth_m": hw.depth_m})
    for c in config.canonical_curves:
        df[c] = hw.curves[c]
        df[f"{c}_mask"] = hw.masks[c]
    for a in config.auxiliary_curves():
        df[a] = hw.aux_curves.get(a)
        df[f"{a}_mask"] = hw.aux_masks.get(a)
    df.to_parquet(out_dir / f"{_safe(hw.well_id)}.parquet", index=False)


def coverage_row(hw: HarmonizedWell, config: HarmonizationConfig) -> dict:
    row = {"well_id": hw.well_id}
    for c in config.canonical_curves:
        row[f"cov_m_{c}"] = round(hw.curve_coverage_m(c), 1)
    return row


def run_batch(
    wells: Iterable[tuple[str, RawWell]],
    config: HarmonizationConfig,
    source: str,
    processed_dir: Path | None = None,
    keep_harmonized: bool = False,
) -> dict:
    """Harmonize + QC each (well_id, RawWell). Returns records/coverage/etc.

    processed_dir: if given, write one parquet per well there.
    keep_harmonized: retain HarmonizedWell objects (only for small sources that
    need norm stats, e.g. FORCE). Off by default for memory safety.
    """
    if processed_dir is not None:
        processed_dir.mkdir(parents=True, exist_ok=True)
    records: list[QCRecord] = []
    coverage: list[dict] = []
    unmapped: list[tuple[str, str, str, str]] = []
    failures: list[tuple[str, str]] = []
    harmonized: list[HarmonizedWell] = []

    for well_id, raw in wells:
        try:
            hw = harmonize_well(raw, config)
            rec = run_well_qc(hw, config)
        except Exception as e:  # noqa: BLE001 - bulk robustness; record and continue
            failures.append((well_id, f"{type(e).__name__}: {e}"))
            continue
        records.append(rec)
        coverage.append(coverage_row(hw, config))
        for mnem, unit in hw.unmapped:
            unmapped.append((source, well_id, mnem, unit))
        if processed_dir is not None:
            write_processed_parquet(hw, config, processed_dir)
        if keep_harmonized:
            harmonized.append(hw)

    return {
        "records": records,
        "coverage": coverage,
        "unmapped": unmapped,
        "failures": failures,
        "harmonized": harmonized,
    }


def write_source_reports(result: dict, source: str, reports_dir: Path) -> dict[str, Path]:
    """Write per-source QC records, coverage, and unmapped CSVs."""
    reports_dir.mkdir(parents=True, exist_ok=True)
    rec_path = reports_dir / f"{source}_qc_records.csv"
    cov_path = reports_dir / f"{source}_coverage.csv"
    unmapped_path = reports_dir / f"{source}_unmapped_mnemonics.csv"

    pd.DataFrame([r.as_row() for r in result["records"]]).to_csv(rec_path, index=False)
    pd.DataFrame(result["coverage"]).to_csv(cov_path, index=False)
    if unmapped_path.exists():
        unmapped_path.unlink()
    write_unmapped_csv(result["unmapped"], unmapped_path)
    return {"records": rec_path, "coverage": cov_path, "unmapped": unmapped_path}


def build_dashboard(
    records: list[QCRecord],
    coverage_rows: list[dict],
    config: HarmonizationConfig,
    out_dir: Path,
    title: str,
    max_heatmap_wells: int = 60,
) -> None:
    """Dashboard PNGs + dark-mode HTML index. Adapts to well count."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    out_dir.mkdir(parents=True, exist_ok=True)
    curves = list(config.canonical_curves)
    cov_df = pd.DataFrame(coverage_rows).set_index("well_id") if coverage_rows else pd.DataFrame()
    n = len(records)

    # Coverage: heatmap for small N, per-curve mean-coverage bar for large N.
    fig, ax = plt.subplots(figsize=(max(6, len(curves) * 0.7), 5))
    if 0 < n <= max_heatmap_wells and not cov_df.empty:
        mat = np.array([[cov_df.loc[w, f"cov_m_{c}"] for c in curves] for w in cov_df.index])
        im = ax.imshow(mat, aspect="auto", cmap="viridis")
        ax.set_xticks(range(len(curves)), curves, rotation=45, ha="right")
        ax.set_yticks(range(len(cov_df.index)), list(cov_df.index), fontsize=6)
        fig.colorbar(im, ax=ax, label="valid metres")
        ax.set_title(f"{title}: curve coverage (valid metres)")
    elif not cov_df.empty:
        means = [cov_df[f"cov_m_{c}"].mean() for c in curves]
        ax.bar(curves, means, color="#4c78a8")
        ax.set_ylabel("mean valid metres")
        ax.set_xticklabels(curves, rotation=45, ha="right")
        ax.set_title(f"{title}: mean curve coverage across {n} wells")
    fig.tight_layout()
    fig.savefig(out_dir / "coverage.png", dpi=120)
    plt.close(fig)

    # Depth coverage histogram.
    lengths = [r.n_grid * config.grid_step_m for r in records]
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.hist(lengths, bins=30, color="#4c78a8")
    ax.set_xlabel("logged interval (m)")
    ax.set_ylabel("wells")
    ax.set_title(f"{title}: depth coverage")
    fig.tight_layout()
    fig.savefig(out_dir / "depth_hist.png", dpi=120)
    plt.close(fig)

    # Washout: per-well bar for small N, histogram for large N.
    wm = [r.washout_interval_m for r in records]
    fig, ax = plt.subplots(figsize=(6, 4))
    if 0 < n <= max_heatmap_wells:
        ax.bar(range(n), wm, color="#e45756")
        ax.set_xticks(range(n), [r.well_id for r in records], rotation=90, fontsize=6)
        ax.set_ylabel("washout interval (m)")
    else:
        ax.hist([w for w in wm if w > 0] or [0], bins=30, color="#e45756")
        ax.set_xlabel("washout interval (m)")
        ax.set_ylabel("wells (with washout)")
    ax.set_title(f"{title}: washout coverage (CALI - BS > threshold)")
    fig.tight_layout()
    fig.savefig(out_dir / "washout.png", dpi=120)
    plt.close(fig)

    passed = sum(1 for r in records if r.min_interval_pass)
    no_bs = sum(1 for r in records if r.no_bitsize)
    washed = sum(1 for r in records if r.washout_flagged and r.washout_interval_m > 0)
    html = f"""<!doctype html><html><head><meta charset="utf-8">
<title>{title} QC dashboard</title>
<style>body{{background:#111;color:#eee;font-family:system-ui,sans-serif;margin:2rem}}
img{{max-width:100%;background:#fff;border-radius:8px;margin:1rem 0}}.k{{color:#8ab4f8}}</style>
</head><body><h1>{title} QC dashboard</h1>
<p>Wells processed: <span class="k">{n}</span>.
Passed minimum-interval: <span class="k">{passed}/{n}</span>.
Washout flagged: <span class="k">{washed}</span>.
No bit size (washout skipped): <span class="k">{no_bs}</span>.</p>
<h2>Curve coverage</h2><img src="coverage.png">
<h2>Depth coverage</h2><img src="depth_hist.png">
<h2>Washout coverage</h2><img src="washout.png">
</body></html>"""
    (out_dir / "index.html").write_text(html, encoding="utf-8")


def merged_pass_count(records_by_source: dict[str, list[QCRecord]]) -> dict:
    """Combined QC-passing counts across sources (Gate G1 evidence)."""
    out = {"per_source": {}, "total_wells": 0, "total_passing": 0}
    for src, recs in records_by_source.items():
        passing = sum(1 for r in recs if r.min_interval_pass)
        out["per_source"][src] = {"wells": len(recs), "qc_passing": passing}
        out["total_wells"] += len(recs)
        out["total_passing"] += passing
    return out


def _noop_iter() -> Iterator[tuple[str, RawWell]]:  # pragma: no cover
    yield from ()
