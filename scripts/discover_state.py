import hashlib, os, subprocess
from pathlib import Path

ROOT = Path("/workspace/LithoGPT-2")
assert ROOT.exists(), f"repo not found at {ROOT}"

def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

print("=== HEAD ===")
print(subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                     capture_output=True, text=True).stdout.strip())

print("\n=== TRACKED FILES (non-code, the evidence surface) ===")
out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True).stdout.split()
interesting = [f for f in out if f.startswith(("configs/", "data/", "reports/", "docs/"))
               or f.endswith((".yaml", ".yml", ".json", ".csv", ".md"))]
assert len(interesting) > 0, "FAIL: zero tracked config/data/report files found"
for f in sorted(interesting):
    print(f"  {f}")
print(f"  [{len(interesting)} files]")

print("\n=== KEY FILE HASHES (Section 3 pins) ===")
for rel in ["data/splits/kgs_coord_crosswalk.csv",
            "configs/force2020/pinned.json",
            "reports/nlog_failures.csv"]:
    p = ROOT / rel
    print(f"  {rel}: {'MISSING' if not p.exists() else sha256(p)[:12] + '  ' + str(p.stat().st_size) + ' bytes'}")

for pat in ["aliases", "alias"]:
    for p in sorted(ROOT.rglob(f"*{pat}*.y*ml")):
        if ".git" not in str(p):
            print(f"  {p.relative_to(ROOT)}: {sha256(p)[:12]}")

print("\n=== PARQUET / RECORDS LOCATIONS (resolved paths, non-zero assertion) ===")
search_roots = [Path("/workspace"), Path("/runpod-volume"), Path("/workspace/data")]
found = 0
for sr in search_roots:
    if not sr.exists():
        print(f"  (absent) {sr}")
        continue
    pqs = list(sr.rglob("*.parquet"))
    csvs = [c for c in sr.rglob("*records*.csv")]
    if pqs or csvs:
        print(f"  {sr}: {len(pqs)} parquet, {len(csvs)} records-csv")
        for c in csvs[:10]:
            print(f"      records -> {c}")
        dirs = sorted({p.parent for p in pqs})[:10]
        for d in dirs:
            print(f"      parquet dir -> {d}  ({len(list(d.glob('*.parquet')))} files)")
        found += len(pqs) + len(csvs)
assert found > 0, "FAIL: zero parquet or records files found on any search root. Volume not attached?"
print(f"\n  TOTAL artifacts located: {found}")

print("\n=== DISK ===")
print(subprocess.run(["df", "-h", "/workspace"], capture_output=True, text=True).stdout)
