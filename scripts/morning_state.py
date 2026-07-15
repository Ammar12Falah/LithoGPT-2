from pathlib import Path
import subprocess

ROOT = Path("/workspace/LithoGPT-2")

def sh(*a):
    return subprocess.run(a, cwd=ROOT, capture_output=True, text=True).stdout.strip()

print("=== HEAD (expect a6d1678) ===")
print(sh("git", "rev-parse", "--short", "HEAD"), sh("git", "log", "-1", "--format=%s"))

print("\n=== CORPUS ON VOLUME ===")
for d, exp in [("data/processed/kgs", 9307), ("data/processed/nlog", 5004),
               ("data/quarantine/nlog_unlogged_20260714", 8)]:
    p = ROOT / d
    n = len(list(p.glob("*.parquet"))) if p.exists() else 0
    print(f"  {d}: {n}  {'OK' if n == exp else 'MISMATCH expected ' + str(exp)}")

print("\n=== FORCE (did last night's fetch land?) ===")
fr = ROOT / "data/raw/force2020"
if fr.exists():
    for f in sorted(fr.iterdir()):
        print(f"  {f.name}  ({f.stat().st_size} bytes)")
    blind = fr / "hidden_test.csv"
    print(f"  BLIND GUARD hidden_test.csv present: {blind.exists()}  <-- must be False")
else:
    print("  data/raw/force2020: ABSENT (fetch did not run last night; will fetch today)")

print("\n=== SPLIT INPUTS (must be committed) ===")
for f in ["data/splits/kgs_coord_crosswalk.csv", "data/raw/nlog/borehole_index.csv",
          "data/splits/kgs_vintage_crosswalk.csv", "reports/nlog_orphan_quarantine.csv"]:
    tracked = f in sh("git", "ls-files").split("\n")
    exists = (ROOT / f).exists()
    print(f"  {f}: on_disk={exists} tracked={tracked}")
