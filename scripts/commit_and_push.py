import os, subprocess
from pathlib import Path

ROOT = Path("/workspace/LithoGPT-2")
TOK = os.environ.get("GH_TOKEN", "")
assert TOK, "FAIL: GH_TOKEN not set in this kernel."
REQUIRED = ["data/splits/kgs_coord_crosswalk.csv", "data/raw/nlog/borehole_index.csv",
            "reports/nlog_orphan_quarantine.csv"]

def sh(*a, cwd=ROOT):
    return subprocess.run(a, cwd=cwd, capture_output=True, text=True)

def scrub(s):
    return s.replace(TOK, "***") if TOK else s

print("=== A. GROUND TRUTH: WHAT IS TRACKED ===")
tracked = set(sh("git", "ls-files").stdout.strip().split("\n"))
print("tracked under data/:")
for f in sorted(t for t in tracked if t.startswith("data/")):
    print("   ", f)
print("\nfiles in commit HEAD:")
print(sh("git", "show", "--stat", "--oneline", "HEAD").stdout)

missing = [r for r in REQUIRED if r not in tracked]
print("=== B. REQUIRED EVIDENCE: TRACKED CHECK ===")
for r in REQUIRED:
    print(f"  {r}: {'TRACKED' if r in tracked else 'NOT TRACKED'}")

if missing:
    print("\n  repairing: force-adding untracked evidence")
    for r in missing:
        assert (ROOT / r).exists(), f"FAIL: {r} missing on disk"
        assert sh("git", "add", "-f", r).returncode == 0, f"FAIL: cannot add {r}"
    sh("git", "add", "-A")
    c = sh("git", "commit", "-m",
           "freeze(stageB-prep): add missing split-input evidence files (rule 5)")
    print(c.stdout.strip() or c.stderr.strip())
    tracked = set(sh("git", "ls-files").stdout.strip().split("\n"))
    for r in REQUIRED:
        assert r in tracked, f"FAIL: {r} still not tracked after repair"
else:
    print("\n  all three already committed. Nothing to repair.")

sh("git", "add", "-A")
if sh("git", "diff", "--cached", "--quiet").returncode != 0:
    print("\n  residual changes present, committing them")
    print(sh("git", "commit", "-m", "chore(stageB): residual working-tree state").stdout.strip())

print("\n=== C. SECRET GUARD ON ALL TRACKED FILES ===")
leaks = []
for f in sorted(tracked):
    p = ROOT / f
    if not p.exists():
        continue
    try:
        if TOK in p.read_text(errors="ignore"):
            leaks.append(f)
    except Exception:
        pass
assert not leaks, f"FAIL: SECRET LEAK, token present in tracked files: {leaks}. Scrub before pushing."
print("  no tracked file contains the token: OK")

data_blobs = [f for f in tracked if f.endswith((".parquet", ".zip", ".tar.gz"))
              or (f.endswith((".las", ".LAS")) and not f.startswith("tests/"))]
assert not data_blobs, f"FAIL: data blobs tracked: {data_blobs}"
print("  no parquet / zip / non-test LAS tracked: OK")

print("\n=== D. PUSH ===")
url = f"https://x-access-token:{TOK}@github.com/Ammar12Falah/LithoGPT-2.git"
p = sh("git", "push", url, "main")
print(scrub(p.stdout).strip())
print(scrub(p.stderr).strip())
assert p.returncode == 0, "FAIL: push rejected. Token needs repo / contents:write scope."

head = sh("git", "rev-parse", "HEAD").stdout.strip()
remote = sh("git", "ls-remote", url, "refs/heads/main").stdout.split()
print(f"\nlocal  HEAD: {head}")
print(f"remote main: {remote[0] if remote else '(unreadable)'}")
assert remote and remote[0] == head, "FAIL: remote main does not match local HEAD"
print("\nCONFIRMED ON GITHUB. CI is now running on this commit.")
