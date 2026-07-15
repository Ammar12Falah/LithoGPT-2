from pathlib import Path

from lithogpt2.ingest._http import FetchLog, PoliteFetcher
from lithogpt2.ingest.force2020 import GH_RAW, SOURCE, _unzip_train, count_wells

ROOT = Path("/workspace/LithoGPT-2")
RAW = ROOT / "data/raw"
dest = RAW / SOURCE

# Rule 9: hidden_test.csv is the blind-10 log data. It is NOT fetched here.
# It is required only by the final scoring path, at the very end of evaluation.
SAFE_FILES = [
    "train.zip",                       # 98 training wells
    "leaderboard_test_features.csv",   # open-10 features
    "leaderboard_test_target.csv",     # open-10 labels
    "penalty_matrix.npy",              # official scoring matrix
]
BLIND = "hidden_test.csv"
assert BLIND not in SAFE_FILES, "FAIL: blind file in the fetch list"

print("fetching (blind-10 data deliberately EXCLUDED, rule 9):")
for f in SAFE_FILES:
    print("  ", f)

fetcher = PoliteFetcher(SOURCE, raw_root=str(RAW))
log = FetchLog()
for f in SAFE_FILES:
    fetcher.fetch(GH_RAW + f, rel_path=f, log=log)

print(f"\nok={len(log.ok)} skipped={len(log.skipped)} failed={len(log.failed)}")
for url, err in log.failed:
    print(f"  FAILED {url}: {err}")
assert not log.failed, "FAIL: some downloads failed"

train_csv = _unzip_train(dest)
assert train_csv and train_csv.exists(), "FAIL: train.csv not extracted"
w, r = count_wells(train_csv)
print(f"\ntrain.csv: {w} wells, {r} rows")
assert w == 98, f"FAIL: expected 98 training wells, got {w}"
assert r == 1170511, f"FAIL: expected 1170511 rows, got {r}"

ot = dest / "leaderboard_test_features.csv"
w2, r2 = count_wells(ot)
print(f"leaderboard_test_features.csv: {w2} wells, {r2} rows")
assert w2 == 10, f"FAIL: expected 10 open-test wells, got {w2}"

print("\nBLIND GUARD:")
bp = dest / BLIND
print(f"  {BLIND} on disk: {bp.exists()}  <-- must be False")
assert not bp.exists(), "FAIL: blind data present on disk"

print("\nCounts reconcile with pinned.json. FORCE raw restored, blind-10 absent.")
print("Files on disk:")
for p in sorted(dest.iterdir()):
    print(f"  {p.name}  ({p.stat().st_size} bytes)")
