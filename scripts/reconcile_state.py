import subprocess, sys
from pathlib import Path
import pandas as pd

ROOT = Path("/workspace/LithoGPT-2")

def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()

print("=== 1. COMMIT IDENTITY ===")
print("branch:", git("rev-parse", "--abbrev-ref", "HEAD"))
print("HEAD  :", git("rev-parse", "HEAD"))
r = subprocess.run(["git", "rev-parse", "--verify", "fe24f20^{commit}"], cwd=ROOT,
                   capture_output=True, text=True)
print("fe24f20 resolves:", "NO (does not exist in this repo)" if r.returncode else "YES -> " + r.stdout.strip())
print("\nlast 5 commits:")
print(git("log", "--oneline", "-5"))
print("\nworking tree (porcelain, empty = clean):")
print(git("status", "--porcelain") or "  CLEAN")

print("\n=== 2. CROSSWALK TRACKING STATUS ===")
tracked_data = git("ls-files", "data/")
print("tracked under data/:", tracked_data or "  NOTHING TRACKED UNDER data/")
ci = subprocess.run(["git", "check-ignore", "-v", "data/splits/kgs_coord_crosswalk.csv"],
                    cwd=ROOT, capture_output=True, text=True)
print("check-ignore:", ci.stdout.strip() or "  not ignored (so it was simply never added)")
gi = ROOT / ".gitignore"
print("\n.gitignore contents:")
print(gi.read_text() if gi.exists() else "  NO .gitignore")

print("\n=== 3. RECORDS CSVs: SHAPE AND OUTCOME COLUMNS ===")
recs = {}
for name, rel in [("kgs", "reports/kgs_qc_records.csv"),
                  ("nlog", "reports/nlog_qc_records.csv"),
                  ("force", "reports/force2020_qc_records.csv")]:
    p = ROOT / rel
    assert p.exists(), f"FAIL: missing {p}"
    df = pd.read_csv(p)
    recs[name] = df
    print(f"\n--- {name}: {p}  shape={df.shape}")
    print("columns:", list(df.columns))
    for c in df.columns:
        if df[c].dtype == bool or (df[c].dtype == object and df[c].nunique(dropna=False) <= 8):
            print(f"   {c}: {df[c].value_counts(dropna=False).to_dict()}")
    assert len(df) > 0, f"FAIL: {name} records is empty"

print("\n=== 4. NLOG PARQUET vs RECORDS DELTA ===")
pq_dir = ROOT / "data/processed/nlog"
stems = {p.stem for p in pq_dir.glob("*.parquet")}
assert len(stems) > 0, "FAIL: zero NLOG parquets at resolved path " + str(pq_dir)
print(f"resolved path: {pq_dir}")
print(f"parquet files: {len(stems)}   records rows: {len(recs['nlog'])}")
print("sample parquet stems:", sorted(stems)[:3])

best = (None, 0.0, set())
for c in recs["nlog"].columns:
    vals = {str(v) for v in recs["nlog"][c].dropna().unique()}
    if not vals:
        continue
    ov = len(vals & stems) / max(len(stems), 1)
    if ov > best[1]:
        best = (c, ov, vals)
print(f"best-matching id column: {best[0]!r}  overlap with parquet stems: {best[1]:.4f}")
if best[0] is not None:
    orphans = sorted(stems - best[2])
    print(f"parquets with NO records row ({len(orphans)}):")
    for o in orphans[:20]:
        print("   ", o)
    missing = sorted(best[2] - stems)
    print(f"records rows with NO parquet ({len(missing)}):")
    for m in missing[:20]:
        print("   ", m)

print("\n=== 5. KGS PARQUET COUNT ===")
kgs_pq = len(list((ROOT / "data/processed/kgs").glob("*.parquet")))
print(f"kgs parquets: {kgs_pq}   kgs records rows: {len(recs['kgs'])}")

print("\n=== 6. UNTRACKED FILES ON POD (evidence at risk) ===")
unt = git("ls-files", "--others", "--exclude-standard")
print(unt or "  none")
print("\n=== 7. IGNORED-BUT-PRESENT DIRS ===")
print(git("status", "--ignored", "--porcelain", "-s") or "  none")
