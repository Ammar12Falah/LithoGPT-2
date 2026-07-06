"""Combined Gate G1 evidence: total QC-passing wells across two continents.

Reads whichever per-source QC record CSVs exist (FORCE = Norway, KGS = Kansas)
and reports the combined QC-passing count, plus a summary dashboard.

    reports/force2020_qc_records.csv  (from scripts/run_qc_force.py)
    reports/kgs_qc_records.csv        (from scripts/run_qc_kgs.py)

Writes reports/qc_combined/index.html and a per-source pass-count figure.
G1 target: 5,000+ QC-passing wells across two continents.
"""

from __future__ import annotations

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

try:
    import matplotlib  # noqa: E402
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # noqa: E402
    _HAS_MPL = True
except Exception:
    _HAS_MPL = False  # viz is non-fatal; combine must run without it
import pandas as pd  # noqa: E402

SOURCES = {
    "force2020": {"label": "FORCE 2020 (Norway, North Sea)", "continent": "Europe"},
    "kgs": {"label": "KGS (Kansas, USA)", "continent": "North America"},
    "nlog": {"label": "NLOG (Netherlands)", "continent": "Europe"},
}
G1_TARGET = 5000


def main() -> None:
    reports = Path("reports")
    rows = []
    continents = set()
    total_wells = total_pass = 0
    for src, meta in SOURCES.items():
        f = reports / f"{src}_qc_records.csv"
        if not f.exists():
            continue
        df = pd.read_csv(f)
        wells = len(df)
        passing = int(df["min_interval_pass"].sum()) if "min_interval_pass" in df else 0
        rows.append({"source": src, "label": meta["label"], "wells": wells,
                     "qc_passing": passing, "continent": meta["continent"]})
        continents.add(meta["continent"])
        total_wells += wells
        total_pass += passing

    if not rows:
        print("No per-source QC record CSVs found. Run run_qc_force.py / run_qc_kgs.py first.")
        return

    print("Combined QC-passing (Gate G1 evidence):")
    for r in rows:
        print(f"  {r['label']:34s} wells={r['wells']:6d}  QC-passing={r['qc_passing']:6d}")
    print(f"  {'TOTAL':34s} wells={total_wells:6d}  QC-passing={total_pass:6d}")
    print(f"  continents: {len(continents)} ({', '.join(sorted(continents))})")
    meets = total_pass >= G1_TARGET and len(continents) >= 2
    print(f"  G1 (>= {G1_TARGET} QC-passing across 2+ continents): "
          f"{'MET' if meets else 'not yet met'}")

    out = reports / "qc_combined"
    out.mkdir(parents=True, exist_ok=True)
    if _HAS_MPL:
        fig, ax = plt.subplots(figsize=(7, 4))
        labels = [r["source"] for r in rows]
        ax.bar(labels, [r["wells"] for r in rows], color="#54617a", label="wells")
        ax.bar(labels, [r["qc_passing"] for r in rows], color="#4c78a8", label="QC-passing")
        ax.axhline(G1_TARGET, color="#e45756", linestyle="--", label=f"G1 target {G1_TARGET}")
        ax.set_ylabel("wells")
        ax.set_title("QC-passing wells by source")
        ax.legend()
        fig.tight_layout()
        fig.savefig(out / "pass_by_source.png", dpi=120)
        plt.close(fig)

    body = "".join(
        f"<tr><td>{r['label']}</td><td>{r['continent']}</td>"
        f"<td>{r['wells']}</td><td>{r['qc_passing']}</td></tr>"
        for r in rows
    )
    html = f"""<!doctype html><html><head><meta charset="utf-8">
<title>Combined QC (Gate G1)</title>
<style>body{{background:#111;color:#eee;font-family:system-ui,sans-serif;margin:2rem}}
table{{border-collapse:collapse;margin:1rem 0}}td,th{{border:1px solid #444;padding:.4rem .8rem}}
img{{max-width:100%;background:#fff;border-radius:8px;margin:1rem 0}}.k{{color:#8ab4f8}}</style>
</head><body><h1>Combined QC: Gate G1 evidence</h1>
<p>Total QC-passing: <span class="k">{total_pass}</span> across
<span class="k">{len(continents)}</span> continents. G1 target: {G1_TARGET}
across 2+ continents. Status: <span class="k">{'MET' if meets else 'not yet met'}</span>.</p>
<table><tr><th>Source</th><th>Continent</th><th>Wells</th><th>QC-passing</th></tr>
{body}<tr><th>TOTAL</th><th>{len(continents)} continents</th><th>{total_wells}</th>
<th>{total_pass}</th></tr></table>
<img src="pass_by_source.png"></body></html>"""
    (out / "index.html").write_text(html, encoding="utf-8")
    print(f"  combined dashboard: {out / 'index.html'}")


if __name__ == "__main__":
    main()
