import subprocess
from pathlib import Path
import pandas as pd
from datetime import datetime

ROOT = Path("/workspace/LithoGPT-2")
pd.set_option("display.width", 200)

print("=== A. CROSSWALK: resolve 100% vs 99.98% ===")
cw = pd.read_csv(ROOT / "data/splits/kgs_coord_crosswalk.csv")
print("path:", ROOT / "data/splits/kgs_coord_crosswalk.csv")
print("shape:", cw.shape)
print("columns:", list(cw.columns))
print(cw.head(3).to_string())
kgs = pd.read_csv(ROOT / "reports/kgs_qc_records.csv")
key = None
for c in cw.columns:
    ov = len(set(cw[c].astype(str)) & set(kgs["well_id"].astype(str)))
    if ov > 0:
        print(f"  column {c!r} overlaps kgs well_id on {ov} values")
        if key is None or ov > 0:
            key = c if ov == max(ov, 0) else key
print("\nnull counts per column:")
print(cw.isna().sum().to_string())

print("\n=== B. THE 8 ORPHAN NLOG PARQUETS ===")
orphans = ["Q08-A-03","Q08-B-01","WYK-13","WYK-16","WYK-17-S1","WYK-34","WYK-35","WYK-36"]
pq_dir = ROOT / "data/processed/nlog"
print("mtimes of orphans vs corpus median:")
all_m = [(p.stem, p.stat().st_mtime, p.stat().st_size) for p in pq_dir.glob("*.parquet")]
assert len(all_m) > 0, "FAIL: no parquets at " + str(pq_dir)
med = sorted(m for _, m, _ in all_m)[len(all_m)//2]
print(f"  corpus median mtime: {datetime.fromtimestamp(med)}")
for stem, m, sz in sorted(all_m):
    if stem in orphans:
        print(f"  {stem:12s} mtime={datetime.fromtimestamp(m)}  size={sz}")

for label, rel in [("current failures", "reports/nlog_failures.csv"),
                   ("current coverage", "reports/nlog_coverage.csv"),
                   ("pre_clear records", "reports/_pre_clear_20260710_194418/nlog_qc_records.csv"),
                   ("pre_alias records", "reports/_pre_alias/nlog_qc_records.csv")]:
    p = ROOT / rel
    if not p.exists():
        print(f"  {label}: MISSING {p}")
        continue
    d = pd.read_csv(p)
    idcol = "well_id" if "well_id" in d.columns else d.columns[0]
    hits = sorted(set(d[idcol].astype(str)) & set(orphans))
    print(f"  {label}: {len(d)} rows, orphans present: {hits if hits else 'NONE'}")

print("\n=== C. PASS PREDICATE (what exactly is min_interval_pass?) ===")
for name, rel in [("kgs","reports/kgs_qc_records.csv"),
                  ("nlog","reports/nlog_qc_records.csv"),
                  ("force","reports/force2020_qc_records.csv")]:
    d = pd.read_csv(ROOT / rel)
    ge3 = d["n_curves_meeting"] >= 3
    mp = d["min_interval_pass"].astype(bool)
    agree = (ge3 == mp).all()
    print(f"  {name}: min_interval_pass == (n_curves_meeting>=3) ? {agree}   "
          f"pass={int(mp.sum())}  n_curves>=3={int(ge3.sum())}")
    print(f"     drop_reason: {d['drop_reason'].value_counts(dropna=False).to_dict()}")

print("\n=== D. WHERE ARE NLOG COORDINATES? (needed for R1 geographic blocks) ===")
cands = []
for p in ROOT.rglob("*.csv"):
    if ".git" in str(p) or "processed" in str(p):
        continue
    try:
        cols = pd.read_csv(p, nrows=1).columns.str.lower().tolist()
    except Exception:
        continue
    if any(k in " ".join(cols) for k in ["lat", "lon", "x_", "easting", "north", "coord", "rd_x", "rd_y"]):
        cands.append((str(p.relative_to(ROOT)), cols))
for path, cols in cands:
    print(f"  {path}\n     {cols}")
data_dir = ROOT / "data"
print("\n  non-parquet files under data/ (ignored by git, may hold the NLOG index):")
for p in sorted(data_dir.rglob("*")):
    if p.is_file() and p.suffix not in (".parquet",):
        print(f"     {p.relative_to(ROOT)}  ({p.stat().st_size} bytes)")

print("\n=== E. UNTRACKED HANDOFF DOC (first 40 lines) ===")
h = ROOT / "docs/HANDOFF_CONTINUING_AGENT.md"
print(h.read_text().split("\n")[:40] if h.exists() else "MISSING")
