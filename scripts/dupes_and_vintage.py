import io
import zipfile
from pathlib import Path

import pandas as pd

ROOT = Path("/workspace/LithoGPT-2")
pd.set_option("display.width", 220)

kgs = pd.read_csv(ROOT / "reports/kgs_qc_records.csv")
kgs["well_id"] = kgs["well_id"].astype(str)
cw = pd.read_csv(ROOT / "data/splits/kgs_coord_crosswalk.csv")
cw["well_id"] = cw["well_id"].astype(str)
cw["well_kgs_id"] = cw["well_kgs_id"].astype(str)
m = kgs.merge(cw, on="well_id", how="left", validate="one_to_one")
p = m[m["min_interval_pass"].astype(bool)].copy()

print("=== 1. DUPLICATE-CONTENT CLASS: EXACT NUMBERS FOR BOTH OPTIONS ===")
d = p[p["dedup_hash"].notna()]
grp = d.groupby("dedup_hash")
sizes = grp.size()
dupg = sizes[sizes > 1]
print(f"  passing KGS logs: {len(p)}")
print(f"  distinct content hashes: {sizes.nunique() if False else int(sizes.index.nunique())}")
print(f"  content hashes with >1 log: {len(dupg)}")
print(f"  logs inside a duplicate group: {int(dupg.sum())}")
print(f"  redundant copies (would be dropped by dedup): {int(dupg.sum() - len(dupg))}")
print(f"\n  OPTION A (keep all, disclose): KGS passing stays {len(p)}")
print(f"  OPTION B (dedup by content):    KGS passing becomes {len(p) - int(dupg.sum() - len(dupg))}")

print("\n  are duplicate copies the SAME physical well or DIFFERENT wells?")
same = grp["well_kgs_id"].nunique()
same = same[sizes > 1]
print(f"    dup groups whose logs all map to ONE physical well: {int((same == 1).sum())}")
print(f"    dup groups spanning MORE THAN ONE physical well:    {int((same > 1).sum())}  <-- these are the interesting ones")
if int((same > 1).sum()):
    bad = same[same > 1].index[:5]
    print("    examples of identical content on different physical wells:")
    print(d[d["dedup_hash"].isin(bad)][["well_id", "well_kgs_id", "dedup_hash", "n_grid", "lat", "lon"]]
          .sort_values("dedup_hash").head(12).to_string(index=False))

print("\n  do duplicate groups ever span >1 township-range cell? (leakage test)")
import re
rx = re.compile(r"T\s*(\d+)\s*([NS])\s*[, ]*\s*R\s*(\d+)\s*([EW])", re.I)
pr = p["plss"].fillna("").str.extract(rx)
pr.columns = ["twp", "twp_dir", "rng", "rng_dir"]
p["tr_cell"] = pr["twp"] + pr["twp_dir"] + "-" + pr["rng"] + pr["rng_dir"]
cells = p[p["dedup_hash"].notna()].groupby("dedup_hash")["tr_cell"].nunique()
cells = cells[sizes > 1]
print(f"    dup groups spanning >1 TR cell: {int((cells > 1).sum())}   <-- must be 0 for splits to be safe")

print("\n=== 2. NLOG DUPLICATE CONTENT (same check) ===")
nl = pd.read_csv(ROOT / "reports/nlog_qc_records.csv")
np_ = nl[nl["min_interval_pass"].astype(bool)]
ns = np_[np_["dedup_hash"].notna()].groupby("dedup_hash").size()
ndup = ns[ns > 1]
print(f"  passing NLOG logs: {len(np_)}")
print(f"  content hashes with >1 log: {len(ndup)}   redundant copies: {int(ndup.sum() - len(ndup))}")

print("\n=== 3. BUILD KGS VINTAGE CROSSWALK (KID -> SPUD, COMPLETION) ===")
print("  parsing ks_wells.txt (204 MB), this is the slow step ...")
with zipfile.ZipFile(ROOT / "data/raw/kgs/ks_wells.zip") as zf:
    member = [n for n in zf.namelist() if n.lower().endswith((".txt", ".csv"))][0]
    raw = zf.read(member)
w = pd.read_csv(io.BytesIO(raw), sep=",", low_memory=False, encoding="latin-1",
                usecols=["KID", "SPUD", "COMPLETION", "TOWNSHIP", "TWN_DIR", "RANGE", "RANGE_DIR"])
print(f"  ks_wells rows: {len(w)}")
w["KID"] = w["KID"].astype(str)

need = set(cw["well_kgs_id"])
w = w[w["KID"].isin(need)].copy()
print(f"  rows matching our {len(need)} physical wells: {len(w)}")
assert len(w) > 0, "FAIL: zero KID matches. well_kgs_id is not ks_wells.KID"

for c in ["SPUD", "COMPLETION"]:
    w[c] = pd.to_datetime(w[c], format="%d-%b-%Y", errors="coerce")
w["vintage_year"] = w["COMPLETION"].dt.year.fillna(w["SPUD"].dt.year)
print(f"  KIDs with a usable vintage year: {int(w['vintage_year'].notna().sum())} of {len(w)}")
print(f"  vintage range: {w['vintage_year'].min():.0f} to {w['vintage_year'].max():.0f}, "
      f"median {w['vintage_year'].median():.0f}")

pv = p.merge(w[["KID", "vintage_year"]], left_on="well_kgs_id", right_on="KID", how="left")
print(f"\n  PASSING KGS logs with a vintage year: {int(pv['vintage_year'].notna().sum())} of {len(pv)} "
      f"({100*pv['vintage_year'].notna().mean():.1f} percent)")
print("  passing logs by decade:")
dec = (pv["vintage_year"] // 10 * 10).value_counts().sort_index()
print(dec.to_string())

out = ROOT / "data/splits/kgs_vintage_crosswalk.csv"
w[["KID", "SPUD", "COMPLETION", "vintage_year"]].to_csv(out, index=False)
print(f"\n  written: {out}  ({len(w)} rows)")

print("\n=== 4. CROSS-CHECK: ks_wells TOWNSHIP/RANGE vs PLSS-PARSED TR CELL ===")
w2 = w.dropna(subset=["TOWNSHIP", "RANGE"]).copy()
w2["tr_from_registry"] = (w2["TOWNSHIP"].astype(int).astype(str) + w2["TWN_DIR"].str.strip()
                          + "-" + w2["RANGE"].astype(int).astype(str) + w2["RANGE_DIR"].str.strip())
chk = p.merge(w2[["KID", "tr_from_registry"]], left_on="well_kgs_id", right_on="KID", how="inner")
agree = (chk["tr_cell"] == chk["tr_from_registry"])
print(f"  comparable logs: {len(chk)}   TR cell agrees with registry: {int(agree.sum())} "
      f"({100*agree.mean():.2f} percent)")
if int((~agree).sum()):
    print("  DISAGREEMENTS (first 8):")
    print(chk[~agree][["well_id", "well_kgs_id", "tr_cell", "tr_from_registry"]].head(8).to_string(index=False))
