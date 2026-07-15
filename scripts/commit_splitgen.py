import os, subprocess
from pathlib import Path

ROOT = Path("/workspace/LithoGPT-2")
TOK = os.environ.get("GH_TOKEN", "")
assert TOK, "FAIL: GH_TOKEN not set in this kernel."

def sh(*a):
    return subprocess.run(a, cwd=ROOT, capture_output=True, text=True)

def scrub(s):
    return s.replace(TOK, "***") if TOK else s

sh("git", "add", "-A")
staged = [s for s in sh("git", "diff", "--cached", "--name-only").stdout.split("\n") if s]
print("=== STAGED ===")
for s in staged:
    print("  ", s)

# secret guard: no token in any staged file
print("\n=== SECRET GUARD ===")
leaks = []
for s in staged:
    p = ROOT / s
    if p.exists():
        try:
            if TOK in p.read_text(errors="ignore"):
                leaks.append(s)
        except Exception:
            pass
assert not leaks, f"FAIL: token in staged files {leaks}"
print("  clean")

# no data blobs
blobs = [s for s in staged if s.endswith((".parquet",".zip",".tar.gz"))
         or (s.lower().endswith(".las") and not s.startswith("tests/"))]
assert not blobs, f"FAIL: data blobs staged {blobs}"
print("  no data blobs staged")

MSG = """freeze(stageB): split-gen code + split assignment (pre-hash)

Spatial splits built in one operation (seed 20260715), all leakage assertions pass:
  KGS physical-well atomicity (5751 wells), KGS/NLOG coordinate atomicity,
  FORCE blind-10 isolated outside all train/dev/test, zero duplicate rows,
  zero cross-source fingerprint collisions.

Holdouts (advisor ruling 2026-07-15: cap ~250 is approximate, integrity > cap):
  KGS test 263 (4.2% of basin, 13 township-range cells)
  NLOG test 341 (14.5% of basin, 9 geographic cells)
  dev: KGS 339, NLOG 257 (spatial blocks inside training basins)
  FORCE: 98 train, 10 open, 10 blind (official split, never re-cut)

Pre-hash forensic checks (advisor-required):
  A) 8 quarantined NLOG orphans fingerprinted against full corpus: 0 match,
     all 8 unexplained. Stay quarantined; card names them excluded-unexplained.
  B) 9 identical-content-different-well KGS groups: 0 straddle train/holdout,
     all sit in train. No silent leakage on the well-identity axis.

Reconciled: NLOG hard-failure count corrected 384 -> 363 in freeze-plan and
progress-report prose (384 was a stale pre-re-fetch 5005-record figure; 363 is
the final-CSV truth in reports/nlog_failures.csv).

FORCE determinism: re-fetch + reprocess of 98 training wells reproduces the
committed QC records exactly (all 98 wells, all 36 columns). End-to-end pipeline
determinism proof from raw public data.

Nothing hashed yet. Manifest hash is the next, separate step.
"""
c = sh("git", "commit", "-m", MSG)
print("\n=== COMMIT ===")
print(scrub(c.stdout).strip() or scrub(c.stderr).strip())

url = f"https://x-access-token:{TOK}@github.com/Ammar12Falah/LithoGPT-2.git"
p = sh("git", "push", url, "main")
print("\n=== PUSH ===")
print(scrub(p.stdout).strip()); print(scrub(p.stderr).strip())
assert p.returncode == 0, "FAIL: push rejected"

head = sh("git", "rev-parse", "HEAD").stdout.strip()
rem = sh("git", "ls-remote", url, "refs/heads/main").stdout.split()
assert rem and rem[0] == head, "FAIL: remote != local HEAD"
print(f"\nSPLIT-GEN COMMIT (will be pinned in the manifest): {head}")
print("On GitHub. Safe to hash against this commit.")
