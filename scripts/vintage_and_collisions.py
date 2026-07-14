import io
import zipfile
from pathlib import Path

import pandas as pd

ROOT = Path("/workspace/LithoGPT-2")
pd.set_option("display.width", 220)

print("=== 1. KGS VINTAGE: WHAT IS IN THE TWO REGISTRY ZIPS? ===")
for z in ["data/raw/kgs/ks_las_files.zip", "data/raw/kgs/ks_wells.zip"]:
    p = ROOT / z
    print(f"\n--- {z}")
    with zipfile.ZipFile(p) as zf:
        for n in zf.namelist()[:8]:
            print("   member:", n, f"({zf.getinfo(n).file_size} bytes)")
        member = [n for n in zf.namelist() if n.lower().endswith((".txt", ".csv"))]
        if not member:
            print("   no csv/txt member")
            continue
        with zf.open(member[0]) as f:
            head = f.read(4000).decode("latin-1", errors="replace")
    lines = head.split("\n")[:3]
    print("   header:", lines[0][:400])
    if len(lines) > 1:
        print("   row1  :", lines[1][:400])

print("\n=== 2. LOAD ks_wells AND LOOK FOR DATE / KID COLUMNS ===")
with zipfile.ZipFile(ROOT / "data/raw/kgs/ks_wells.zip") as zf:
    member = [n for n in zf.namelist() if n.lower().endswith((".txt", ".csv"))][0]
    with zf.open(member) as f:
        raw = f.read()
for sep in [",", "\t", "|"]:
    try:
        w = pd.read_csv(io.BytesIO(raw), sep=sep, nrows=200, low_memory=False,
                        encoding="latin-1")
        if w.shape[1] > 3:
            print(f"  parsed with sep={sep!r}: {w.shape[1]} columns")
            break
    except Exception as e:
        print(f"  sep={sep!r} failed: {type(e).__name__}")
print("  columns:", list(w.columns))
datec = [c for c in w.columns if any(k in c.lower() for k in
         ["date", "year", "spud", "complet", "log", "td_"])]
kidc = [c for c in w.columns if "kid" in c.lower() or "id" in c.lower()]
print("  date-ish columns:", datec)
print("  id-ish columns  :", kidc)
if datec:
    print("\n  sample of date-ish columns:")
    print(w[datec].head(5).to_string(index=False))

print("\n=== 3. CROSS-SOURCE DUPLICATE FINGERPRINT (Section 5 step 3 precheck) ===")
frames = []
for name, rel in [("kgs", "reports/kgs_qc_records.csv"),
                  ("nlog", "reports/nlog_qc_records.csv"),
                  ("force", "reports/force2020_qc_records.csv")]:
    d = pd.read_csv(ROOT / rel)
    d["src"] = name
    frames.append(d[["well_id", "src", "dedup_hash", "min_interval_pass", "n_grid"]])
allr = pd.concat(frames, ignore_index=True)
p = allr[allr["min_interval_pass"].astype(bool)]
print(f"  passing records across all sources: {len(p)}")
h = p["dedup_hash"].dropna()
print(f"  non-null dedup_hash: {len(h)}   distinct: {h.nunique()}")
dupe = p[p["dedup_hash"].notna() & p["dedup_hash"].duplicated(keep=False)]
print(f"  records sharing a dedup_hash: {len(dupe)}")
if len(dupe):
    g = dupe.groupby("dedup_hash")["src"].nunique()
    cross = g[g > 1]
    print(f"  hashes spanning MORE THAN ONE source: {len(cross)}  <-- must be 0")
    print("  within-source duplicate examples:")
    print(dupe.sort_values("dedup_hash").head(10).to_string(index=False))

print("\n=== 4. BLOCK ATOMICITY: CAN A PHYSICAL WELL STRADDLE TWO TR CELLS? ===")
import re
cw = pd.read_csv(ROOT / "data/splits/kgs_coord_crosswalk.csv")
cw["well_id"] = cw["well_id"].astype(str)
kgs = pd.read_csv(ROOT / "reports/kgs_qc_records.csv")
kgs["well_id"] = kgs["well_id"].astype(str)
m = kgs[kgs["min_interval_pass"].astype(bool)].merge(cw, on="well_id", how="left")
rx = re.compile(r"T\s*(\d+)\s*([NS])\s*[, ]*\s*R\s*(\d+)\s*([EW])", re.I)
pr = m["plss"].fillna("").str.extract(rx)
pr.columns = ["twp", "twp_dir", "rng", "rng_dir"]
m["tr_cell"] = (pr["twp"] + pr["twp_dir"] + "-" + pr["rng"] + pr["rng_dir"])
ok = m["tr_cell"].notna()
g = m[ok].groupby("well_kgs_id")["tr_cell"].nunique()
straddle = g[g > 1]
print(f"  passing logs with a parsed TR cell: {int(ok.sum())}")
print(f"  physical wells spanning >1 TR cell: {len(straddle)}   <-- must be 0")
if len(straddle):
    print(straddle.head(10).to_string())
gc = m[ok].groupby("well_kgs_id")["lat"].nunique()
print(f"  physical wells with >1 distinct latitude: {int((gc > 1).sum())}   <-- must be 0")

print("\n=== 5. NLOG: COORDINATE COLLISIONS ACROSS DIFFERENT NAMES ===")
nl = pd.read_csv(ROOT / "reports/nlog_qc_records.csv")
nl["well_id"] = nl["well_id"].astype(str)
bi = pd.read_csv(ROOT / "data/raw/nlog/borehole_index.csv")
bi["well_id"] = bi["well_id"].astype(str)
n = nl[nl["min_interval_pass"].astype(bool)].merge(
    bi[["well_id", "lon", "lat", "on_offshore"]], on="well_id", how="left")
n["ck"] = n["lat"].round(5).astype(str) + "," + n["lon"].round(5).astype(str)
col = n.groupby("ck")["well_id"].apply(list)
multi = col[col.apply(len) > 1]
print(f"  coordinate points carrying >1 passing log: {len(multi)}")
print("  examples (these MUST land in the same block):")
for ck, ids in list(multi.items())[:6]:
    print(f"    {ck}: {ids}")
