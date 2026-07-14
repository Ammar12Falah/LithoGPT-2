import json, subprocess
from pathlib import Path
import pandas as pd
import pyarrow.parquet as pq

ROOT = Path("/workspace/LithoGPT-2")
ORPH = ["Q08-A-03","Q08-B-01","WYK-13","WYK-16","WYK-17-S1","WYK-34","WYK-35","WYK-36"]

print("=== A. THE 2 KGS WELLS WITH NO COORDINATES ===")
kgs = pd.read_csv(ROOT / "reports/kgs_qc_records.csv")
cw = pd.read_csv(ROOT / "data/splits/kgs_coord_crosswalk.csv")
missing = set(kgs["well_id"].astype(str)) - set(cw["well_id"].astype(str))
assert len(missing) == 2, f"FAIL: expected 2 uncoordinated wells, found {len(missing)}"
sub = kgs[kgs["well_id"].astype(str).isin(missing)]
print(sub[["well_id","n_curves_meeting","min_interval_pass","drop_reason"]].to_string(index=False))
print("=> R2 residual routing only matters if these PASS. passing:",
      int(sub["min_interval_pass"].astype(bool).sum()), "of 2")

print("\n=== B. WHICH 8 ROWS WERE ADDED TO RECORDS SINCE _pre_clear? ===")
cur = pd.read_csv(ROOT / "reports/nlog_qc_records.csv")
pre = pd.read_csv(ROOT / "reports/_pre_clear_20260710_194418/nlog_qc_records.csv")
added = sorted(set(cur["well_id"].astype(str)) - set(pre["well_id"].astype(str)))
removed = sorted(set(pre["well_id"].astype(str)) - set(cur["well_id"].astype(str)))
print(f"added ({len(added)}): {added}")
print(f"removed ({len(removed)}): {removed}")
print("overlap of added with the 8 orphans:", sorted(set(added) & set(ORPH)) or "NONE")

print("\n=== C. ARE THE ORPHANS IN THE NLOG SOURCE INDEX AND FETCH MANIFEST? ===")
bi = pd.read_csv(ROOT / "data/raw/nlog/borehole_index.csv")
print("borehole_index rows:", len(bi))
hit = bi[bi["well_id"].astype(str).isin(ORPH)]
print(f"orphans present in borehole_index: {len(hit)} of 8")
if len(hit):
    print(hit[["well_id","borehole_name","on_offshore","lon","lat","public_as_of"]].to_string(index=False))

man = json.loads((ROOT / "data/raw/nlog/_manifest.json").read_text())
print("\n_manifest.json top-level type:", type(man).__name__,
      "| keys or len:", list(man)[:6] if isinstance(man, dict) else len(man))
flat = json.dumps(man)
for o in ORPH:
    print(f"   {o:12s} appears in fetch manifest: {o in flat}")

print("\n=== D. SCHEMA: ORPHANS vs A KNOWN-GOOD NLOG PARQUET ===")
good_id = str(cur["well_id"].iloc[0])
good = pq.read_schema(ROOT / f"data/processed/nlog/{good_id}.parquet")
gset = set(good.names)
print(f"reference well {good_id}: {len(gset)} cols")
print("  cols:", sorted(gset))
for o in ORPH:
    p = ROOT / f"data/processed/nlog/{o}.parquet"
    s = pq.read_schema(p)
    oset = set(s.names)
    print(f"  {o:12s} cols={len(oset):3d}  identical_to_reference={oset == gset}"
          + ("" if oset == gset else f"  extra={sorted(oset-gset)} missing={sorted(gset-oset)}"))
    md = s.metadata
    print(f"      parquet key-value metadata: {dict(md) if md else 'NONE'}")

print("\n=== E. WHICH RUN WROTE THEM? (grep logs) ===")
logs = sorted((ROOT / "logs").glob("*"))
print("log files:", [l.name for l in logs])
for o in ORPH:
    r = subprocess.run(["grep", "-rl", o, str(ROOT / "logs")], capture_output=True, text=True)
    print(f"  {o:12s} -> {r.stdout.strip().replace(str(ROOT)+'/', '') or 'not in any log'}")
r = subprocess.run(["grep", "-rn", "WYK-34", str(ROOT / "logs")], capture_output=True, text=True)
print("\ncontext lines for WYK-34:")
print("\n".join(r.stdout.strip().split("\n")[:12]) or "  none")

print("\n=== F. SENTINEL/RAIL CHECK ON ORPHANS (were they cleaned?) ===")
RAILS = {"RDEP": 100000.0, "RMED": 100000.0, "RSHA": 100000.0}
for o in ORPH[:3] + [good_id]:
    p = ROOT / f"data/processed/nlog/{o}.parquet"
    df = pq.read_table(p).to_pandas()
    hits = {c: int((df[c] >= v).sum()) for c, v in RAILS.items() if c in df.columns}
    tag = "REFERENCE" if o == good_id else "orphan"
    print(f"  {tag:9s} {o:12s} rows={len(df):6d}  at-or-above-rail counts={hits}")
