import json
import subprocess
from pathlib import Path

import pandas as pd

ROOT = Path("/workspace/LithoGPT-2")

print("=== 1. IS ANY FORCE DATA ON DISK? ===")
for d in ["data/processed/force2020", "data/processed/force", "data/raw/force2020", "data/raw/force"]:
    p = ROOT / d
    print(f"  {d}: {'EXISTS, ' + str(len(list(p.glob('*')))) + ' entries' if p.exists() else 'ABSENT'}")

print("\n  all directories under data/:")
for p in sorted((ROOT / "data").iterdir()):
    if p.is_dir():
        sub = [f"{c.name}({len(list(c.glob('*')))})" for c in sorted(p.iterdir()) if c.is_dir()]
        print(f"    {p.name}/  -> {sub or '(no subdirs)'}")

print("\n  parquet census by directory:")
total = 0
for p in sorted(ROOT.rglob("*.parquet")):
    pass
dirs = {}
for p in ROOT.rglob("*.parquet"):
    dirs[p.parent] = dirs.get(p.parent, 0) + 1
    total += 1
for d, n in sorted(dirs.items()):
    print(f"    {d.relative_to(ROOT)}: {n}")
print(f"    TOTAL: {total}")

print("\n  any FORCE-ish file anywhere (csv/zip/las):")
hits = [p for p in ROOT.rglob("*")
        if p.is_file() and "force" in p.name.lower()
        and p.suffix.lower() in (".csv", ".zip", ".las", ".npy", ".json")]
for h in hits:
    print(f"    {h.relative_to(ROOT)}  ({h.stat().st_size} bytes)")
if not hits:
    print("    NONE")

print("\n=== 2. WHERE ARE THE OPEN-10 AND BLIND-10 WELL NAMES? ===")
pin = json.loads((ROOT / "configs/force2020/pinned.json").read_text())
flat = json.dumps(pin)
print("  pinned.json full text search for a names list:")
for key in ["open_test_wells", "hidden_test_wells", "blind", "well_names", "wells"]:
    print(f"    contains {key!r}: {key in flat}")
print("\n  full pinned.json:")
print(json.dumps(pin, indent=2)[:2500])

print("\n  grep the whole repo for a known FORCE well-name pattern (NO/xx-xx-x):")
r = subprocess.run(["grep", "-rlE", r"1[5-6]/[0-9]+-[0-9]+", str(ROOT),
                    "--include=*.json", "--include=*.csv", "--include=*.md",
                    "--include=*.py", "--include=*.yaml", "--include=*.txt"],
                   capture_output=True, text=True)
print(r.stdout or "    no file contains FORCE-style well names")

print("\n=== 3. WHAT DO THE 98 FORCE QC RECORDS SAY? ===")
f = pd.read_csv(ROOT / "reports/force2020_qc_records.csv")
print(f"  rows: {len(f)}")
print(f"  well_id sample: {list(f['well_id'].head(5))}")
print(f"  all 98 distinct: {f['well_id'].is_unique}")

print("\n=== 4. FORCE NORM STATS (provisional, replaced at step 5) ===")
ns = json.loads((ROOT / "configs/force2020/norm_stats.json").read_text())
print("  keys:", list(ns)[:12])

print("\n=== 5. VERDICT ===")
fp = ROOT / "data/processed/force2020"
have_data = fp.exists() and len(list(fp.glob("*.parquet"))) > 0
have_names = any(k in flat for k in ["open_test_wells", "hidden_test_wells"]) and "15/9-" in flat
print(f"  FORCE processed parquets present: {have_data}")
print(f"  FORCE open-10 / blind-10 names present in repo: {have_names}")
if not have_data or not have_names:
    print("\n  BLOCKER: Section 5 step 2 needs the FORCE open-10 and blind-10 NAMES to")
    print("  build and exclude those splits. Step 5 needs the 98 training wells' DATA")
    print("  to compute norm stats. Re-fetch required before the freeze can proceed.")
    print("  Rule 9 stands: blind-10 NAMES may be read; blind-10 DATA is never loaded.")
