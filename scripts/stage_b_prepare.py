import hashlib, shutil, subprocess
from datetime import datetime
from pathlib import Path
import pandas as pd

ROOT = Path("/workspace/LithoGPT-2")
ORPH = ["Q08-A-03","Q08-B-01","WYK-13","WYK-16","WYK-17-S1","WYK-34","WYK-35","WYK-36"]

def sh(*a, cwd=ROOT):
    return subprocess.run(a, cwd=cwd, capture_output=True, text=True)

def trackable(rel):
    """Authoritative test. git add --dry-run exits non-zero on an ignored path.
    NOTE: git check-ignore is NOT usable here; its exit code counts matched
    patterns including negations, so it reports '!foo' as a match."""
    r = sh("git", "add", "--dry-run", rel)
    return r.returncode == 0

def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()

# ---------- 1. verify .gitignore intent ----------
print("=== 1. GITIGNORE VERIFICATION (git add --dry-run) ===")
MUST_TRACK = ["data/splits/kgs_coord_crosswalk.csv", "data/raw/nlog/borehole_index.csv"]
MUST_IGNORE = ["data/processed/nlog/A05-01.parquet", "data/raw/nlog/log_index.csv",
               "data/raw/kgs/ks_wells.zip"]
for rel in MUST_TRACK:
    ok = trackable(rel)
    print(f"  MUST TRACK  {rel}: {'TRACKABLE' if ok else 'STILL IGNORED'}")
    assert ok, f"FAIL: {rel} is ignored and must not be"
for rel in MUST_IGNORE:
    ok = trackable(rel)
    print(f"  MUST IGNORE {rel}: {'LEAKING INTO GIT' if ok else 'correctly ignored'}")
    assert not ok, f"FAIL: {rel} became trackable; gitignore is too permissive"
sh("git", "reset")  # undo any staging the dry-run may have implied

# ---------- 2. quarantine the 8 unlogged parquets ----------
print("\n=== 2. ORPHAN QUARANTINE ===")
src_dir = ROOT / "data/processed/nlog"
qdir = ROOT / "data/quarantine/nlog_unlogged_20260714"
qdir.mkdir(parents=True, exist_ok=True)
bi = pd.read_csv(ROOT / "data/raw/nlog/borehole_index.csv")
rows = []
for o in ORPH:
    p = src_dir / f"{o}.parquet"
    if not p.exists():
        print(f"  {o}: already quarantined, skipping")
        continue
    h = sha256(p)
    b = bi[bi["well_id"].astype(str) == o].iloc[0]
    rows.append({
        "well_id": o, "sha256": h, "size_bytes": p.stat().st_size,
        "mtime_utc": datetime.utcfromtimestamp(p.stat().st_mtime).isoformat(),
        "lon": b["lon"], "lat": b["lat"], "on_offshore": b["on_offshore"],
        "in_borehole_index": True, "in_fetch_manifest": True,
        "in_qc_records": False, "in_any_log": False,
        "exclusion_reason": "written outside any logged pipeline run; no QC record; provenance untraceable (operating rule 2)",
    })
    shutil.move(str(p), str(qdir / p.name))
    print(f"  quarantined {o}  sha256={h[:12]}")
if rows:
    pd.DataFrame(rows).to_csv(ROOT / "reports/nlog_orphan_quarantine.csv", index=False)
    print(f"  manifest written: reports/nlog_orphan_quarantine.csv")

remaining = len(list(src_dir.glob("*.parquet")))
recs = len(pd.read_csv(ROOT / "reports/nlog_qc_records.csv"))
print(f"\n  nlog parquets now: {remaining}   records rows: {recs}")
assert remaining == recs == 5004, f"FAIL: expected 5004 == 5004, got {remaining} vs {recs}"
print("  RECONCILED: parquet directory and QC roster agree exactly.")

# ---------- 3. name the scratch notebooks ----------
print("\n=== 3. NOTEBOOKS ===")
a = ROOT / "reports/alias_audit/Untitled.ipynb"
if a.exists():
    a.rename(ROOT / "reports/alias_audit/cali_isolation_diagnostic.ipynb")
    print("  Untitled.ipynb -> cali_isolation_diagnostic.ipynb (the R4 rationale)")
else:
    print("  Untitled.ipynb: already renamed or absent")
b = ROOT / "reports/alias_audit/Untitled1.ipynb"
if b.exists():
    b.unlink()
    print("  Untitled1.ipynb deleted (its CI check becomes scripts/ci_status.py)")

# ---------- 4. run exactly what CI runs ----------
print("\n=== 4. CI-EQUIVALENT GATE ===")
r = sh("ruff", "check", "src", "tests")
print("ruff:", r.stdout.strip() or "(clean)", "| exit", r.returncode)
t = sh("pytest", "-q")
print("pytest:", t.stdout.strip().split("\n")[-1], "| exit", t.returncode)
print("\n  GATE " + ("PASSED. Safe to commit and push." if r.returncode == 0 and t.returncode == 0
                     else "FAILED. Do not commit."))

print("\n=== 5. WHAT WOULD BE COMMITTED ===")
print(sh("git", "status", "--short").stdout)
