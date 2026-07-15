import sys
sys.path.insert(0, "/workspace/LithoGPT-2/src")

import hashlib
from pathlib import Path
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

ROOT = Path("/workspace/LithoGPT-2")

def curve_fingerprint(path, cols=("GR","RHOB","NPHI","DTC","RDEP")):
    """Content hash over available canonical curves, order-stable, NaN-aware."""
    t = pq.read_table(path)
    names = set(t.column_names)
    h = hashlib.sha256()
    for c in cols:
        if c in names:
            a = np.asarray(t.column(c).to_numpy(zero_copy_only=False), dtype="float64")
            h.update(c.encode())
            h.update(np.nan_to_num(a, nan=-9999.25).round(4).tobytes())
    return h.hexdigest()

# ================= CHECK A: the 8 orphans =================
print("=== CHECK A: are the 8 quarantined orphans duplicates or unexplained? ===")
qdir = ROOT / "data/quarantine/nlog_unlogged_20260714"
orphans = sorted(qdir.glob("*.parquet"))
print(f"  quarantined parquets: {len(orphans)}")

orphan_fp = {}
for p in orphans:
    orphan_fp[p.stem] = curve_fingerprint(p)
    print(f"    {p.stem:14s} fp={orphan_fp[p.stem][:16]}")

# fingerprint the full NLOG and KGS corpus
print("\n  fingerprinting corpus (nlog + kgs) for comparison ...")
corpus_fp = {}
for src in ["nlog", "kgs"]:
    d = ROOT / f"data/processed/{src}"
    for p in d.glob("*.parquet"):
        corpus_fp.setdefault(curve_fingerprint(p), []).append(f"{src}/{p.stem}")

print("\n  orphan -> corpus match:")
a_matches, a_unexplained = [], []
for stem, fp in orphan_fp.items():
    hit = corpus_fp.get(fp, [])
    if hit:
        print(f"    {stem:14s} DUPLICATE of {hit}")
        a_matches.append((stem, hit))
    else:
        print(f"    {stem:14s} NO MATCH in corpus (unexplained)")
        a_unexplained.append(stem)
print(f"\n  VERDICT A: {len(a_matches)} are duplicates of existing wells, "
      f"{len(a_unexplained)} are unexplained")
print(f"    card language: {'excluded-duplicate' if not a_unexplained else 'excluded-unexplained for ' + str(a_unexplained)}")

# ================= CHECK B: the 9 cross-well-identical groups =================
print("\n=== CHECK B: do identical-content different-well KGS pairs straddle train/holdout? ===")
kgs = pd.read_csv(ROOT / "reports/kgs_qc_records.csv")
kgs["well_id"] = kgs["well_id"].astype(str)
kgs = kgs[kgs["min_interval_pass"].astype(bool)]
cw = pd.read_csv(ROOT / "data/splits/kgs_coord_crosswalk.csv")
cw["well_id"] = cw["well_id"].astype(str); cw["well_kgs_id"] = cw["well_kgs_id"].astype(str)
km = kgs.merge(cw[["well_id","well_kgs_id"]], on="well_id", how="left")

# find groups: same dedup_hash, >1 DISTINCT physical well
g = km.dropna(subset=["dedup_hash"]).groupby("dedup_hash")["well_kgs_id"].nunique()
cross_well_hashes = g[g > 1].index.tolist()
print(f"  dedup_hash groups spanning >1 physical well: {len(cross_well_hashes)}")

# load the split assignment we just built
split = pd.read_csv(ROOT / "data/splits/split_assignment.csv")
split["well_id"] = split["well_id"].astype(str)
split_map = dict(zip(split["well_id"], split["split"]))

leaks = []
for dh in cross_well_hashes:
    members = km[km["dedup_hash"] == dh]["well_id"].tolist()
    splits_hit = {w: split_map.get(w, "MISSING") for w in members}
    distinct = set(splits_hit.values())
    holdout = {s for s in distinct if s.startswith("test") or s == "dev"}
    train = {"train"} & distinct
    flag = "  <-- STRADDLES train/holdout" if (holdout and train) else ""
    print(f"    {dh[:16]}: {splits_hit}{flag}")
    if holdout and train:
        leaks.append((dh, splits_hit))

print(f"\n  VERDICT B: {len(leaks)} cross-well-identical groups straddle train and a holdout")
if leaks:
    print("  *** SILENT LEAKAGE. These must be forced to one split before the hash. ***")
    for dh, sh in leaks:
        print(f"    {dh[:16]}: {sh}")
else:
    print("  none straddle. Splits are clean on this axis too.")

print("\n=== SUMMARY ===")
print(f"  A: 8 orphans -> {len(a_matches)} duplicate, {len(a_unexplained)} unexplained")
print(f"  B: {len(leaks)} leakage straddles among {len(cross_well_hashes)} cross-well groups")
print("  " + ("BOTH CLEAR. Proceed to reconcile then hash." if not leaks
             else "CHECK B FAILED. Fix split placement before hashing."))
