import sys
sys.path.insert(0, "/workspace/LithoGPT-2/src")

import re
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/workspace/LithoGPT-2")
SEED = 20260715
pd.set_option("display.width", 200)
FRAC, CAP, FLOOR = 0.10, 250, 100   # cap is approximate per advisor ruling 2026-07-15

def safe_name(w):
    return re.sub(r"[ /\\]", "_", str(w))

# ================================================================ KGS
kgs = pd.read_csv(ROOT / "reports/kgs_qc_records.csv")
kgs["well_id"] = kgs["well_id"].astype(str)
kgs = kgs[kgs["min_interval_pass"].astype(bool)].copy()
cw = pd.read_csv(ROOT / "data/splits/kgs_coord_crosswalk.csv")
cw["well_id"] = cw["well_id"].astype(str); cw["well_kgs_id"] = cw["well_kgs_id"].astype(str)
vt = pd.read_csv(ROOT / "data/splits/kgs_vintage_crosswalk.csv")
vt["KID"] = vt["KID"].astype(str)
k = kgs.merge(cw, on="well_id", how="left").merge(
    vt[["KID","vintage_year"]], left_on="well_kgs_id", right_on="KID", how="left")
rx = re.compile(r"T\s*(\d+)\s*([NS])\s*[, ]*\s*R\s*(\d+)\s*([EW])", re.I)
pr = k["plss"].fillna("").str.extract(rx)
k["tr_cell"] = pr[0] + pr[1] + "-" + pr[2] + pr[3]
k["decade"] = (k["vintage_year"] // 10 * 10)
print(f"KGS passing: {len(k)}   uncoordinated->train (R2): {int(k['tr_cell'].isna().sum())}")

cell_stats = k[k["tr_cell"].notna()].groupby("tr_cell").agg(n=("well_id","size"), md=("decade","median")).reset_index()
target = min(CAP, max(FLOOR, round(len(k)*FRAC)))
order = cell_stats.sample(frac=1.0, random_state=SEED).sort_values("md")
chosen, got = [], 0
for _, row in order.iterrows():
    if got >= target: break
    chosen.append(row["tr_cell"]); got += int(row["n"])
kgs_holdout = set(chosen)
k["split"] = np.where(k["tr_cell"].isin(kgs_holdout), "test_kgs", "train")
print(f"  KGS holdout: {int((k['split']=='test_kgs').sum())} across {len(kgs_holdout)} tr-cells")

csize = cell_stats.set_index("tr_cell")["n"].to_dict()
train_cells = [c for c in cell_stats["tr_cell"] if c not in kgs_holdout]
dev_order = pd.Series(train_cells).sample(frac=1.0, random_state=SEED+1)
dev_cells, dg = [], 0
for c in dev_order:
    if dg >= round(len(k)*0.05): break
    dev_cells.append(c); dg += int(csize[c])
k.loc[k["tr_cell"].isin(dev_cells), "split"] = "dev"
print(f"  KGS dev: {int((k['split']=='dev').sum())} across {len(dev_cells)} tr-cells")

# ================================================================ NLOG
nl = pd.read_csv(ROOT / "reports/nlog_qc_records.csv")
nl["well_id"] = nl["well_id"].astype(str)
nl = nl[nl["min_interval_pass"].astype(bool)].copy()
bi = pd.read_csv(ROOT / "data/raw/nlog/borehole_index.csv")
bi["well_id"] = bi["well_id"].astype(str)
n = nl.merge(bi[["well_id","lon","lat","on_offshore","public_as_of"]], on="well_id", how="left")
assert n["lon"].notna().all(), "FAIL: NLOG well without coordinates"
n["geo_cell"] = (np.floor(n["lat"]*2)/2).astype(str)+"_"+(np.floor(n["lon"]*2)/2).astype(str)
n["decade"] = (pd.to_datetime(n["public_as_of"], errors="coerce").dt.year // 10 * 10)
n_target = min(CAP, max(FLOOR, round(len(n)*FRAC)))
gstats = n.groupby("geo_cell").agg(nn=("well_id","size"), md=("decade","median")).reset_index()
gorder = gstats.sample(frac=1.0, random_state=SEED+2).sort_values("md")
nchosen, ng = [], 0
for _, row in gorder.iterrows():
    if ng >= n_target: break
    nchosen.append(row["geo_cell"]); ng += int(row["nn"])
nlog_holdout = set(nchosen)
n["split"] = np.where(n["geo_cell"].isin(nlog_holdout), "test_nlog", "train")
gsize = gstats.set_index("geo_cell")["nn"].to_dict()
ntrain = [c for c in gstats["geo_cell"] if c not in nlog_holdout]
ndev_order = pd.Series(ntrain).sample(frac=1.0, random_state=SEED+3)
ndev, ndg = [], 0
for c in ndev_order:
    if ndg >= round(len(n)*0.05): break
    ndev.append(c); ndg += int(gsize[c])
n.loc[n["geo_cell"].isin(ndev), "split"] = "dev"
print(f"NLOG passing: {len(n)}   holdout: {int((n['split']=='test_nlog').sum())} across {len(nlog_holdout)} geo-cells   dev: {int((n['split']=='dev').sum())}")

# ================================================================ FORCE
train_ids = set(pd.read_csv(ROOT / "reports/force2020_qc_records.csv")["well_id"].astype(str))
open10 = {'15/9-14','25/10-10','25/11-24','25/5-3','29/3-1','34/10-16 R','34/3-3 A','34/6-1 S','35/6-2 S','35/9-8'}
blind10 = {'15/9-23','16/2-7','16/7-6','17/4-1','25/10-9','31/2-10','31/2-21 S','34/3-2 S','35/11-5','35/9-7'}
assert len(train_ids) == 98 and not (train_ids & open10) and not (train_ids & blind10) and not (open10 & blind10)
force_rows = ([(w,"force2020","train") for w in sorted(train_ids)]
              + [(w,"force2020","test_force_open") for w in sorted(open10)]
              + [(w,"force2020","blind_force") for w in sorted(blind10)])
force = pd.DataFrame(force_rows, columns=["well_id","source","split"])
force["lat"] = np.nan; force["lon"] = np.nan
print(f"FORCE: train 98, open 10, blind 10")

# ================================================================ ASSEMBLE
k["source"] = "kgs"; n["source"] = "nlog"
cols = ["well_id","source","split","lat","lon"]
allw = pd.concat([k[cols], n[cols], force[cols]], ignore_index=True)
allw["safe_name"] = allw["well_id"].map(safe_name)

# ================================================================ ASSERTIONS
print("\n=== LEAKAGE ASSERTIONS ===")
kwell = k.dropna(subset=["well_kgs_id"]).groupby("well_kgs_id")["split"].nunique()
assert (kwell == 1).all(); print(f"  KGS {len(kwell)} physical wells atomic: OK")
kc = k.dropna(subset=["lat","lon"]).copy(); kc["ck"] = kc["lat"].round(6).astype(str)+","+kc["lon"].round(6).astype(str)
assert (kc.groupby("ck")["split"].nunique() == 1).all(); print("  KGS coord atomicity: OK")
n["ck"] = n["lat"].round(5).astype(str)+","+n["lon"].round(5).astype(str)
assert (n.groupby("ck")["split"].nunique() == 1).all(); print("  NLOG coord atomicity: OK")
assert set(force[force.split=="blind_force"]["well_id"]) == blind10; print("  FORCE blind-10 isolated: OK")
assert allw.duplicated(subset=["well_id","source"]).sum() == 0; print("  no duplicate rows: OK")

# soft cap check per advisor ruling: record, do not fail
print("\n=== HOLDOUT SIZING (cap ~250 approximate; integrity > cap) ===")
for s, base in [("test_kgs", len(k)), ("test_nlog", len(n))]:
    c = int((allw.split==s).sum())
    print(f"  {s}: {c} wells = {100*c/base:.1f}% of basin  (floor {FLOOR}, cap ~{CAP})")
    assert c >= FLOOR, f"FAIL: {s}={c} below floor {FLOOR}"

# cross-source collision
allq = []
for src, rel in [("kgs","reports/kgs_qc_records.csv"),("nlog","reports/nlog_qc_records.csv"),("force2020","reports/force2020_qc_records.csv")]:
    d = pd.read_csv(ROOT / rel); d["well_id"] = d["well_id"].astype(str); d["src"] = src
    allq.append(d[d["min_interval_pass"].astype(bool)][["well_id","src","dedup_hash"]])
aq = pd.concat(allq, ignore_index=True)
cross = aq.dropna(subset=["dedup_hash"]).groupby("dedup_hash")["src"].nunique()
assert (cross <= 1).all(); print("  zero cross-source collisions: OK")

# ================================================================ WRITE (NO HASH)
out = ROOT / "data/splits/split_assignment.csv"
allw.to_csv(out, index=False)
print(f"\n=== WRITTEN (not hashed): {out} ===")
print(allw.groupby(["source","split"]).size().unstack(fill_value=0).to_string())
print(f"\nTOTAL: {len(allw)}   seed {SEED}")
