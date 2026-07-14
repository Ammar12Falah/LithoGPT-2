import json
import re
import subprocess
from pathlib import Path

import pandas as pd

ROOT = Path("/workspace/LithoGPT-2")
pd.set_option("display.width", 200)

def sh(*a):
    return subprocess.run(a, cwd=ROOT, capture_output=True, text=True).stdout.strip()

print("=== 0. VERIFY DECISION CAPTURE d31379f EXISTS (precondition, not assumed) ===")
r = subprocess.run(["git", "rev-parse", "--verify", "d31379f^{commit}"],
                   cwd=ROOT, capture_output=True, text=True)
if r.returncode == 0:
    print("  d31379f RESOLVES ->", r.stdout.strip()[:12])
    print("  subject:", sh("git", "log", "-1", "--format=%s", "d31379f"))
    print("  date   :", sh("git", "log", "-1", "--format=%ci", "d31379f"))
    print("  files  :", sh("git", "show", "--stat", "--format=", "d31379f"))
else:
    print("  *** d31379f DOES NOT RESOLVE IN THIS REPO ***")
    print("  searching commit subjects for the architecture decision capture:")
    print(sh("git", "log", "--oneline", "--all", "--grep=decision", "-i"))
    print(sh("git", "log", "--oneline", "--all", "--grep=architect", "-i"))
    print("  DECISIONS_LOG.md last modified in:", sh("git", "log", "-1", "--format=%h %ci %s", "--", "docs/DECISIONS_LOG.md"))

print("\n=== 1a. KGS SAME-WELL: LAS-file KIDs sharing one physical well ===")
cw = pd.read_csv(ROOT / "data/splits/kgs_coord_crosswalk.csv")
kgs = pd.read_csv(ROOT / "reports/kgs_qc_records.csv")
kgs["well_id"] = kgs["well_id"].astype(str)
cw["well_id"] = cw["well_id"].astype(str)
cw["well_kgs_id"] = cw["well_kgs_id"].astype(str)

m = kgs.merge(cw, on="well_id", how="left", validate="one_to_one")
assert len(m) == len(kgs), "FAIL: crosswalk join changed row count"
n_logs = len(m)
n_wells = m["well_kgs_id"].nunique(dropna=True)
print(f"  KGS log records (LAS files): {n_logs}")
print(f"  distinct physical wells (well_kgs_id): {n_wells}  (+{m['well_kgs_id'].isna().sum()} with no coordinate row)")
dup = m["well_kgs_id"].value_counts()
dup = dup[dup > 1]
print(f"  physical wells with MORE THAN ONE log: {len(dup)}")
if len(dup):
    print(f"  logs involved in a multi-log well: {int(dup.sum())}")
    print(f"  max logs on a single well: {int(dup.max())}")
    print("  distribution of logs-per-well (for wells with >1):")
    print(dup.value_counts().sort_index().to_string())

passing = m[m["min_interval_pass"].astype(bool)]
p_logs = len(passing)
p_wells = passing["well_kgs_id"].nunique(dropna=True)
print(f"\n  PASSING: {p_logs} logs from {p_wells} distinct wells"
      + (f"  (+{int(passing['well_kgs_id'].isna().sum())} uncoordinated)" if passing["well_kgs_id"].isna().any() else ""))

print("\n  same-coordinate check (belt and braces):")
pc = passing.dropna(subset=["lat", "lon"]).copy()
pc["coordkey"] = pc["lat"].round(6).astype(str) + "," + pc["lon"].round(6).astype(str)
cd = pc["coordkey"].value_counts()
print(f"    distinct coordinate points among passing: {pc['coordkey'].nunique()}")
print(f"    coordinate points carrying >1 log: {int((cd > 1).sum())}")

print("\n=== 1b. NLOG SAME-WELL: borehole id uniqueness ===")
nl = pd.read_csv(ROOT / "reports/nlog_qc_records.csv")
nl["well_id"] = nl["well_id"].astype(str)
print(f"  records rows: {len(nl)}   distinct well_id: {nl['well_id'].nunique()}")
assert nl["well_id"].is_unique, "FAIL: NLOG well_id is NOT unique in records"
print("  well_id is unique: one record per borehole")

bi = pd.read_csv(ROOT / "data/raw/nlog/borehole_index.csv")
bi["well_id"] = bi["well_id"].astype(str)
nlp = nl[nl["min_interval_pass"].astype(bool)].merge(
    bi[["well_id", "lon", "lat", "on_offshore", "public_as_of", "borehole_name"]],
    on="well_id", how="left", validate="one_to_one")
print(f"  PASSING nlog: {len(nlp)}   with coordinates: {int(nlp['lon'].notna().sum())}"
      f"   MISSING coordinates: {int(nlp['lon'].isna().sum())}")
print(f"  on_offshore split: {nlp['on_offshore'].value_counts(dropna=False).to_dict()}")

print("\n  sidetrack families (name stem before -S<n>), a same-well proxy:")
stem = nlp["well_id"].str.replace(r"-S\d+$", "", regex=True)
sd = stem.value_counts()
print(f"    distinct stems among {len(nlp)} passing: {stem.nunique()}")
print(f"    stems carrying >1 log: {int((sd > 1).sum())}   logs involved: {int(sd[sd > 1].sum())}")

nc = nlp.dropna(subset=["lat", "lon"]).copy()
nc["coordkey"] = nc["lat"].round(6).astype(str) + "," + nc["lon"].round(6).astype(str)
ncd = nc["coordkey"].value_counts()
print(f"    distinct coordinate points: {nc['coordkey'].nunique()}   points with >1 log: {int((ncd > 1).sum())}")

print("\n=== 2. KGS PLSS GRID (input for township-range blocking, R1) ===")
pl = passing["plss"].dropna()
print(f"  passing wells with a PLSS string: {len(pl)} of {p_logs}")
print("  sample:", pl.iloc[0] if len(pl) else "(none)")
rx = re.compile(r"T\s*(\d+)\s*([NS])\s*[, ]*\s*R\s*(\d+)\s*([EW])", re.I)
parsed = pl.str.extract(rx)
parsed.columns = ["twp", "twp_dir", "rng", "rng_dir"]
ok = parsed.notna().all(axis=1)
print(f"  PLSS strings parsing to township-range: {int(ok.sum())} ({100*ok.mean():.2f} percent)")
if int(ok.sum()) < len(pl):
    print("  UNPARSED samples:")
    for s in pl[~ok].head(5):
        print("     ", repr(s))
tr = (parsed.loc[ok, "twp"] + parsed.loc[ok, "twp_dir"] + "-"
      + parsed.loc[ok, "rng"] + parsed.loc[ok, "rng_dir"])
print(f"  distinct township-range cells: {tr.nunique()}")
cnt = tr.value_counts()
print(f"  wells per cell: median {int(cnt.median())}, mean {cnt.mean():.1f}, max {int(cnt.max())}")
print(f"  target holdout ~10 percent of {p_logs} = ~{round(p_logs*0.10)} wells, capped at 250")
print("  top 12 cells by well count:")
print(cnt.head(12).to_string())

print("\n=== 3. NLOG GEOGRAPHY (input for geographic blocking, R1) ===")
print(nlp[["lon", "lat"]].describe().loc[["min", "25%", "50%", "75%", "max"]].to_string())
print(f"  target holdout ~10 percent of {len(nlp)} = ~{round(len(nlp)*0.10)} wells, floor 100, cap 250")

print("\n=== 4. FORCE PINNED SPLIT (names only, blind data NEVER loaded) ===")
pin = json.loads((ROOT / "configs/force2020/pinned.json").read_text())
print("  keys:", list(pin))
for k, v in pin.items():
    if isinstance(v, list):
        print(f"  {k}: {len(v)} entries -> {v[:3]}{' ...' if len(v) > 3 else ''}")
    else:
        print(f"  {k}: {v}")

print("\n=== 5. VINTAGE (for R1 vintage-stratified blocks, and the card's 44-to-36 tail) ===")
for name, df, col in [("nlog", nlp, "public_as_of")]:
    if col in df.columns:
        yr = pd.to_datetime(df[col], errors="coerce").dt.year
        print(f"  {name} {col} year: min {yr.min():.0f} max {yr.max():.0f} median {yr.median():.0f}, missing {int(yr.isna().sum())}")
kcols = [c for c in m.columns if "year" in c.lower() or "date" in c.lower() or "vintage" in c.lower()]
print(f"  KGS records columns carrying a date or year: {kcols or 'NONE (vintage must come from elsewhere)'}")
